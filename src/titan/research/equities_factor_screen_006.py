"""EQ-006: Turnover-Constrained Quality & Low-Vol Factor Screen.

Research-only. Evaluates the composite Quality-LowVol factor with a rebalance
deadband (hysteresis buffer) to minimize portfolio turnover friction and meet
ADR-029/ADR-030/ADR-031 governance hurdles.

Preserves deterministic boundaries: zero execution/broker/engine imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from titan.backtest.factor_simulator import (
    FactorCostModel,
    FactorSimulationResult,
    VenueCostSchedule,
    simulate_factor_portfolio,
)
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseData,
    EquitiesUniverseManifest,
)
from titan.research.factors import (
    cross_sectional_zscore,
    factor_low_volatility,
    factor_quality_lowvol,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
HYP_DIR = _REPO_ROOT / "research" / "equities" / "hypotheses"
RESULTS_DIR = _REPO_ROOT / "research" / "equities" / "results"


@dataclass(frozen=True)
class FactorPreRegistration:
    hypothesis_id: str
    factor_name: str
    universe: list[str]
    parameters: dict[str, Any]
    cost_label: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    pass_criteria: dict[str, Any]

    def missing_fields(self) -> list[str]:
        missing = []
        for f in (
            "hypothesis_id",
            "factor_name",
            "universe",
            "parameters",
            "cost_label",
            "is_partition",
            "oos_partition",
            "pass_criteria",
        ):
            if not getattr(self, f):
                missing.append(f)
        return missing

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "FactorPreRegistration":
        return FactorPreRegistration(
            hypothesis_id=data.get("hypothesis_id", ""),
            factor_name=data.get("factor_name", ""),
            universe=list(data.get("universe", [])),
            parameters=dict(data.get("parameters", {})),
            cost_label=data.get("cost_label", ""),
            is_partition=dict(data.get("is_partition", {})),
            oos_partition=dict(data.get("oos_partition", {})),
            pass_criteria=dict(data.get("pass_criteria", {})),
        )


def load_factor_preregistration(path: str | Path) -> FactorPreRegistration:
    with open(path, encoding="utf-8") as fh:
        return FactorPreRegistration.from_dict(json.load(fh))


def _compute_max_drawdown(returns: pd.Series) -> float:
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(abs(dd.min())) if len(dd) else 0.0


def simulate_factor_portfolio_deadband(
    universe: EquitiesUniverseData,
    factor_scores: pd.DataFrame,
    *,
    hypothesis_id: str,
    partition: str = "OOS",
    top_k: int = 3,
    bottom_k: int = 3,
    rebalance_freq_days: int = 21,
    entry_pct: float = 0.20,
    exit_pct: float = 0.40,
    gross_exposure: float = 1.0,
    cost_model: VenueCostSchedule | None = None,
) -> FactorSimulationResult:
    """Simulates a dollar-neutral factor portfolio with a rebalance deadband.

    Deadband Logic:
    - Long Leg:
      - Retain existing long assets if their percentile rank remains >= (1 - exit_pct).
      - If retained < top_k, add candidate assets from top entry percentile (rank >= 1 - entry_pct).
    - Short Leg:
      - Retain existing short assets if their percentile rank remains <= exit_pct.
      - If retained < bottom_k, add candidate assets from bottom entry percentile (rank <= entry_pct).
    """
    cost = cost_model or VenueCostSchedule.standard_us_equity()
    prices = universe.prices
    returns = universe.returns

    # Align dates
    common_index = prices.index.intersection(factor_scores.index)
    prices = prices.loc[common_index]
    returns = returns.loc[common_index]
    factor_scores = factor_scores.loc[common_index]

    n_bars = len(common_index)
    if n_bars < rebalance_freq_days + 5:
        raise ValueError("insufficient data points to simulate factor portfolio")

    target_leg_weight = gross_exposure / 2.0
    rebalance_dates = common_index[::rebalance_freq_days]
    reb_weights = pd.DataFrame(index=rebalance_dates, columns=prices.columns, dtype=float)

    current_longs: list[str] = []
    current_shorts: list[str] = []


    for reb_date in rebalance_dates:
        scores = factor_scores.loc[reb_date].dropna()
        n_assets = len(scores)
        if n_assets < top_k + bottom_k:
            reb_weights.loc[reb_date] = pd.Series(0.0, index=prices.columns)
            continue

        # Compute percentile ranks (1.0 = highest score / best, 0.0 = lowest score / worst)
        # Using rank(ascending=True) -> 1 to N, normalized to (rank - 1) / (N - 1)
        ranks = scores.rank(ascending=True)
        if n_assets > 1:
            pct_ranks = (ranks - 1.0) / (n_assets - 1.0)
        else:
            pct_ranks = pd.Series(0.5, index=scores.index)

        # 1. Update Long Leg
        # Long entry threshold: pct_rank >= 1.0 - entry_pct (e.g. top 20% -> >= 0.80)
        # Long exit threshold: pct_rank < 1.0 - exit_pct (e.g. drops below top 40% -> < 0.60)
        long_exit_thresh = 1.0 - exit_pct
        long_entry_thresh = 1.0 - entry_pct

        # Retain existing longs that have not breached exit threshold
        retained_longs = [
            sym for sym in current_longs
            if sym in pct_ranks.index and pct_ranks[sym] >= long_exit_thresh
        ]

        # If below capacity, fill from top candidate entrants
        if len(retained_longs) < top_k:
            candidate_longs = [
                sym for sym in scores.sort_values(ascending=False).index
                if sym not in retained_longs and pct_ranks[sym] >= long_entry_thresh
            ]
            for cand in candidate_longs:
                retained_longs.append(cand)
                if len(retained_longs) >= top_k:
                    break

        # If above capacity, keep the highest ranked among retained
        if len(retained_longs) > top_k:
            retained_longs = scores.loc[retained_longs].sort_values(ascending=False).index[:top_k].tolist()

        current_longs = retained_longs

        # 2. Update Short Leg
        # Short entry threshold: pct_rank <= entry_pct (e.g. bottom 20% -> <= 0.20)
        # Short exit threshold: pct_rank > exit_pct (e.g. rises above bottom 40% -> > 0.40)
        short_exit_thresh = exit_pct
        short_entry_thresh = entry_pct

        # Retain existing shorts that have not breached exit threshold
        retained_shorts = [
            sym for sym in current_shorts
            if sym in pct_ranks.index and pct_ranks[sym] <= short_exit_thresh
        ]

        # If below capacity, fill from bottom candidate entrants
        if len(retained_shorts) < bottom_k:
            candidate_shorts = [
                sym for sym in scores.sort_values(ascending=True).index
                if sym not in retained_shorts and pct_ranks[sym] <= short_entry_thresh
            ]
            for cand in candidate_shorts:
                retained_shorts.append(cand)
                if len(retained_shorts) >= bottom_k:
                    break

        # If above capacity, keep the lowest ranked among retained
        if len(retained_shorts) > bottom_k:
            retained_shorts = scores.loc[retained_shorts].sort_values(ascending=True).index[:bottom_k].tolist()

        current_shorts = retained_shorts

        # 3. Assign target weights
        w = pd.Series(0.0, index=prices.columns)
        if current_longs:
            long_wt = target_leg_weight / len(current_longs)
            for sym in current_longs:
                w[sym] += long_wt

        if current_shorts:
            short_wt = target_leg_weight / len(current_shorts)
            for sym in current_shorts:
                w[sym] -= short_wt

        reb_weights.loc[reb_date] = w

    # Forward fill weights between rebalances across the entire daily timeline
    weights = reb_weights.reindex(common_index).ffill().fillna(0.0)


    # Shift weights by 1 day for strictly causal point-in-time t+1 execution
    held_weights = weights.shift(1).fillna(0.0)

    # Returns decomposition
    long_w = held_weights.clip(lower=0.0)
    short_w = held_weights.clip(upper=0.0)

    long_daily = (long_w * returns).sum(axis=1)
    short_daily = (short_w * returns).sum(axis=1)
    gross_daily = long_daily + short_daily

    # Costs calculation
    # 1. Short borrow fee: accrued daily on short leg
    daily_borrow_rate = (cost.annual_short_borrow_bps * 1e-4) / 252.0
    borrow_costs = short_w.abs().sum(axis=1) * daily_borrow_rate

    # 2. Rebalance friction
    delta_w = weights.diff().abs().sum(axis=1).fillna(0.0)
    comm_rate = cost.commission_per_share_usd / cost.assumed_avg_share_price
    commission_costs = delta_w * comm_rate
    spread_costs = delta_w * (cost.spread_bps * 1e-4)
    slippage_costs = delta_w * (cost.slippage_bps * 1e-4)
    regulatory_costs = delta_w * (cost.regulatory_fees_bps * 1e-4)

    total_friction = borrow_costs + commission_costs + spread_costs + slippage_costs + regulatory_costs
    net_daily = gross_daily - total_friction

    # Summary performance metrics
    mean_net = float(net_daily.mean())
    std_net = float(net_daily.std())
    ann_sharpe = (mean_net / std_net * np.sqrt(252.0)) if std_net > 0 else 0.0
    ann_return = mean_net * 252.0
    max_dd = _compute_max_drawdown(net_daily)

    # Monthly turnover: sum(delta_w) / (n_days / 21)
    monthly_turnover = float(delta_w.sum() / max(n_bars / 21.0, 1.0))

    # Rank Information Coefficient (IC)
    fwd_21d_returns = prices.pct_change(rebalance_freq_days).shift(-rebalance_freq_days)
    ic_values: list[float] = []

    for reb_date in rebalance_dates[:-1]:
        f_slice = factor_scores.loc[reb_date].dropna()
        r_slice = fwd_21d_returns.loc[reb_date].dropna()
        common_syms = f_slice.index.intersection(r_slice.index)
        if len(common_syms) >= 4:
            f_vals = f_slice[common_syms]
            r_vals = r_slice[common_syms]
            if float(f_vals.std()) > 1e-8 and float(r_vals.std()) > 1e-8:
                corr, _ = spearmanr(f_vals, r_vals)
                if not np.isnan(corr):
                    ic_values.append(float(corr))

    mean_ic = float(np.mean(ic_values)) if ic_values else 0.0
    ic_pos_frac = float(sum(1 for x in ic_values if x > 0) / len(ic_values)) if ic_values else 0.0

    q_returns = {
        "long_leg_ann": round(float(long_daily.mean() * 252.0), 4),
        "short_leg_ann": round(float(short_daily.mean() * 252.0), 4),
        "gross_spread_ann": round(float(gross_daily.mean() * 252.0), 4),
        "net_spread_ann": round(ann_return, 4),
    }

    return FactorSimulationResult(
        hypothesis_id=hypothesis_id,
        partition=partition,
        net_returns=net_daily,
        gross_returns=gross_daily,
        long_returns=long_daily,
        short_returns=short_daily,
        turnover_series=delta_w,
        rank_ic_series=pd.Series(ic_values),
        costs={
            "total_borrow_cost": float(borrow_costs.sum()),
            "total_commissions": float(commission_costs.sum()),
            "total_spread": float(spread_costs.sum()),
            "total_slippage": float(slippage_costs.sum()),
            "total_regulatory_fees": float(regulatory_costs.sum()),
            "total_friction": float(total_friction.sum()),
        },
        annualized_net_sharpe=ann_sharpe,
        annualized_net_return=ann_return,
        max_drawdown=max_dd,
        monthly_turnover=monthly_turnover,
        mean_rank_ic=mean_ic,
        ic_positive_fraction=ic_pos_frac,
        quantile_returns=q_returns,
        cost_schedule=cost,
    )


def verify_quantile_monotonicity(
    universe: EquitiesUniverseData,
    factor_scores: pd.DataFrame,
    *,
    top_k: int = 3,
    bottom_k: int = 3,
    holding_days: int = 21,
) -> tuple[bool, dict[str, float]]:
    """Calculates forward holding-period returns across top, middle, and bottom quantiles."""
    prices = universe.prices
    reb_dates = prices.index[::holding_days]
    top_rets, mid_rets, bot_rets = [], [], []

    for d in reb_dates[:-1]:
        scores = factor_scores.loc[d].dropna()
        if len(scores) < top_k + bottom_k + 1:
            continue
        sorted_syms = scores.sort_values(ascending=False).index
        fwd_slice = prices.loc[d:]
        if len(fwd_slice) <= holding_days:
            continue
        fwd_ret = (fwd_slice.iloc[holding_days] - fwd_slice.iloc[0]) / fwd_slice.iloc[0]

        top_syms = sorted_syms[:top_k]
        bot_syms = sorted_syms[-bottom_k:]
        mid_syms = sorted_syms[top_k:-bottom_k]

        top_rets.append(float(fwd_ret[top_syms].mean()))
        if len(mid_syms) > 0:
            mid_rets.append(float(fwd_ret[mid_syms].mean()))
        bot_rets.append(float(fwd_ret[bot_syms].mean()))

    ann_factor = 252.0 / float(holding_days)
    avg_top = float(np.mean(top_rets)) * ann_factor if top_rets else 0.0
    avg_mid = float(np.mean(mid_rets)) * ann_factor if mid_rets else 0.0
    avg_bot = float(np.mean(bot_rets)) * ann_factor if bot_rets else 0.0

    # Strict monotonicity: Top > Mid > Bottom; minimal monotonicity: Top > Bottom
    is_monotonic = bool(avg_top > avg_mid > avg_bot) if mid_rets else bool(avg_top > avg_bot)

    spreads = {
        "top_quantile_ann": round(avg_top, 4),
        "mid_quantile_ann": round(avg_mid, 4),
        "bot_quantile_ann": round(avg_bot, 4),
        "is_monotonic": is_monotonic,
    }
    return is_monotonic, spreads


def evaluate_factor_gates_006(
    oos_res: FactorSimulationResult,
    adverse_res: FactorSimulationResult,
    prereg: FactorPreRegistration,
    *,
    is_monotonic: bool = False,
    replicated: bool = False,
    is_res: FactorSimulationResult | None = None,
) -> dict[str, Any]:
    """Evaluates frozen decision gates for EQ-006 and classifies outcome per AGENTS.md Rule 8."""
    min_sharpe = float(prereg.pass_criteria.get("min_oos_net_sharpe", 1.0))
    min_ic_pos = float(prereg.pass_criteria.get("min_ic_positive_frac", 0.70))
    min_mean_ic = float(prereg.pass_criteria.get("min_mean_rank_ic", 0.05))
    max_turnover = float(prereg.pass_criteria.get("max_monthly_turnover", 0.20))
    target_turnover = float(prereg.pass_criteria.get("target_monthly_turnover", 0.15))
    max_dd = float(prereg.pass_criteria.get("max_drawdown", 0.12))

    gates = {
        "oos_net_sharpe": bool(oos_res.annualized_net_sharpe >= min_sharpe),
        "rank_ic_fraction": bool(oos_res.ic_positive_fraction >= min_ic_pos),
        "rank_ic_magnitude": bool(oos_res.mean_rank_ic >= min_mean_ic),
        "max_drawdown": bool(oos_res.max_drawdown <= max_dd),
        "turnover_capacity": bool(oos_res.monthly_turnover <= max_turnover),
        "target_turnover_enforced": bool(oos_res.monthly_turnover <= target_turnover),
        "quantile_monotonicity": bool(is_monotonic),
        "adverse_net_positive": bool(adverse_res.annualized_net_return > 0.0),
        "replication": bool(replicated),
    }

    all_passed = all(gates.values())
    verdict = "candidate" if all_passed else "negative_result"

    # Rule 8 Failure Mode Attribution
    failure_mode = ""
    failure_mode_basis = ""
    failure_mode_confidence = "high"
    disambiguation = ""

    if not all_passed:
        # Check why it failed
        gross_spread = oos_res.quantile_returns.get("gross_spread_ann", 0.0)
        net_ret = oos_res.annualized_net_return

        if gross_spread > 0.0 and net_ret <= 0.0:
            failure_mode = "execution_constrained_rejection"
            failure_mode_basis = (
                f"Gross economic spread exists (+{gross_spread:.2%}) but turnover friction "
                f"(-{oos_res.costs['total_friction']:.4f}) dragged net return negative (-{net_ret:.2%})."
            )
            disambiguation = "Friction destroyed positive gross alpha. Mechanism valid but unharvestable."
        elif is_res is not None and is_res.annualized_net_sharpe >= min_sharpe and oos_res.annualized_net_sharpe < min_sharpe:
            failure_mode = "overfit_regime_fragile"
            failure_mode_basis = (
                f"In-sample performance (Sharpe {is_res.annualized_net_sharpe:.2f}) failed to generalize "
                f"to out-of-sample partition (Sharpe {oos_res.annualized_net_sharpe:.2f} < {min_sharpe:.2f})."
            )
            disambiguation = "Edge in 2020-2022 broke down under 2023-2024 out-of-sample regime."
        else:
            failure_mode = "mechanism_failure"
            reasons = []
            if not gates["oos_net_sharpe"]:
                reasons.append(f"Net Sharpe {oos_res.annualized_net_sharpe:.2f} < {min_sharpe:.2f}")
            if not gates["rank_ic_fraction"]:
                reasons.append(f"IC positive fraction {oos_res.ic_positive_fraction:.1%} < {min_ic_pos:.1%}")
            if not gates["rank_ic_magnitude"]:
                reasons.append(f"Mean Rank IC {oos_res.mean_rank_ic:+.3f} < {min_mean_ic:+.3f}")
            if not gates["quantile_monotonicity"]:
                reasons.append("Quantile monotonicity violated")
            if not gates["max_drawdown"]:
                reasons.append(f"Max DD {oos_res.max_drawdown:.2%} > {max_dd:.2%}")
            failure_mode_basis = (
                f"Turnover-constrained Quality & Low-Vol factor failed statistical hurdles: "
                f"{'; '.join(reasons)}."
            )
            disambiguation = "The underlying factor theory lacks sufficient cross-sectional predictive power."

    res: dict[str, Any] = {
        "verdict": verdict,
        "gates": gates,
        "metrics": {
            "annualized_net_sharpe": oos_res.annualized_net_sharpe,
            "annualized_net_return": oos_res.annualized_net_return,
            "mean_rank_ic": oos_res.mean_rank_ic,
            "ic_positive_fraction": oos_res.ic_positive_fraction,
            "monthly_turnover": oos_res.monthly_turnover,
            "max_drawdown": oos_res.max_drawdown,
            "adverse_annualized_net_return": adverse_res.annualized_net_return,
        },
    }

    if failure_mode:
        res["failure_mode"] = failure_mode
        res["failure_mode_basis"] = failure_mode_basis
        res["failure_mode_confidence"] = failure_mode_confidence
        res["disambiguation"] = disambiguation

    return res


def run_factor_screen_006(
    universe: EquitiesUniverseData,
    prereg: FactorPreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Runs the complete EQ-006 factor screen with deadband simulation and evidence bundle export."""
    missing = prereg.missing_fields()
    if missing:
        raise EquitiesDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise EquitiesDataError("OOS partition cannot be used for parameter choice")

    prices = universe.prices
    params = prereg.parameters

    vol_window = int(params.get("vol_window_days", 63))
    quality_lb = int(params.get("quality_lookback_days", 252))
    skip_days = int(params.get("skip_days", 21))
    w_lv = float(params.get("weight_lowvol", 0.5))
    w_q = float(params.get("weight_quality", 0.5))
    top_k = int(params.get("top_k", 3))
    bottom_k = int(params.get("bottom_k", 3))
    reb_freq = int(params.get("rebalance_freq_days", 21))
    entry_pct = float(params.get("entry_percentile", 0.20))
    exit_pct = float(params.get("exit_percentile", 0.40))

    # 1. Compute factor scores
    scores = factor_quality_lowvol(
        prices,
        vol_window=vol_window,
        quality_lookback=quality_lb,
        skip=skip_days,
        weight_lowvol=w_lv,
        weight_quality=w_q,
    )

    # 2. Slice Partitions
    is_univ = universe.slice_partition("IS")
    oos_univ = universe.slice_partition("OOS")

    # 3. Simulate In-Sample (with deadband)
    is_res = simulate_factor_portfolio_deadband(
        is_univ,
        scores.loc[is_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="IS",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        entry_pct=entry_pct,
        exit_pct=exit_pct,
        cost_model=FactorCostModel.standard_us_equity(),
    )

    # 4. Simulate Out-of-Sample (with deadband)
    oos_res = simulate_factor_portfolio_deadband(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        entry_pct=entry_pct,
        exit_pct=exit_pct,
        cost_model=FactorCostModel.standard_us_equity(),
    )

    # 5. Simulate Out-of-Sample without deadband (baseline comparator for turnover reduction)
    oos_unconstrained_res = simulate_factor_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS_UNCONSTRAINED",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        cost_model=FactorCostModel.standard_us_equity(),
    )

    # 6. Adverse Stress OOS simulation
    adverse_res = simulate_factor_portfolio_deadband(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS_ADVERSE",
        top_k=top_k,
        bottom_k=bottom_k,
        rebalance_freq_days=reb_freq,
        entry_pct=entry_pct,
        exit_pct=exit_pct,
        cost_model=FactorCostModel.stressed_adverse(),
    )

    # 7. Quantile Monotonicity Verification
    is_mono, mono_spreads = verify_quantile_monotonicity(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=reb_freq,
    )

    # 8. Decision Gate Evaluation
    gates_eval = evaluate_factor_gates_006(
        oos_res,
        adverse_res,
        prereg,
        is_monotonic=is_mono,
        replicated=replicated,
        is_res=is_res,
    )

    turnover_reduction_pct = (
        (oos_unconstrained_res.monthly_turnover - oos_res.monthly_turnover)
        / oos_unconstrained_res.monthly_turnover
    ) if oos_unconstrained_res.monthly_turnover > 0 else 0.0

    bundle = {
        "hypothesis_id": prereg.hypothesis_id,
        "factor_name": prereg.factor_name,
        "manifest_digest": universe.manifest.digest(),
        "is": is_res.to_dict(),
        "oos": oos_res.to_dict(),
        "oos_unconstrained_comparator": {
            "monthly_turnover": oos_unconstrained_res.monthly_turnover,
            "annualized_net_sharpe": oos_unconstrained_res.annualized_net_sharpe,
            "annualized_net_return": oos_unconstrained_res.annualized_net_return,
            "turnover_reduction_pct": round(turnover_reduction_pct, 4),
        },
        "adverse_oos": adverse_res.to_dict(),
        "monotonicity": mono_spreads,
        "gates": gates_eval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / f"{prereg.hypothesis_id}-evidence-bundle.json"
    out_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    return bundle
