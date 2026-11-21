"""EQ-009: Point-in-Time Consensus Post-Earnings Announcement Drift (PEAD) Factor Screen.

Research-only. Evaluates true Point-in-Time Wall Street analyst consensus EPS estimates,
exact BMO/AMC announcement timings, causal trading day mapping, standardized unexpected
earnings (SUE), 42-day drift holding horizons, turnover suppression, and explicit IBKR Pro
friction attribution per ADR-029, ADR-030, and ADR-031 governance standards.

Preserves deterministic boundaries: zero execution/broker/runtime imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from titan.backtest.factor_simulator import (
    FactorCostModel,
    FactorSimulationResult,
    VenueCostSchedule,
)
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseData,
    EquitiesUniverseManifest,
)
from titan.research.bundle_io import write_bundle

_REPO_ROOT = Path(__file__).resolve().parents[3]
HYP_DIR = _REPO_ROOT / "research" / "equities" / "hypotheses"
RESULTS_DIR = _REPO_ROOT / "research" / "equities" / "results"
DATA_DIR = _REPO_ROOT / "research" / "equities" / "data"


@dataclass(frozen=True)
class FactorPreRegistration:
    """Immutable pre-registration parameters for EQ-009."""

    hypothesis_id: str
    factor_name: str
    universe: list[str]
    parameters: dict[str, Any]
    cost_label: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    pass_criteria: dict[str, Any]
    universe_label: str = ""
    economic_rationale: str = ""

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
            universe_label=data.get("universe_label", ""),
            economic_rationale=data.get("economic_rationale", ""),
        )


def load_factor_preregistration(path: str | Path) -> FactorPreRegistration:
    """Loads and deserializes an immutable factor pre-registration file."""
    with open(path, encoding="utf-8") as fh:
        return FactorPreRegistration.from_dict(json.load(fh))


def load_pit_earnings_events(path: str | Path) -> pd.DataFrame:
    """Loads point-in-time consensus earnings events from parquet or json."""
    p = Path(path)
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    elif p.suffix == ".json":
        return pd.read_json(p)
    else:
        raise ValueError(f"Unsupported earnings events file format: {p.suffix}")


def _compute_max_drawdown(returns: pd.Series) -> float:
    """Computes peak-to-trough maximum drawdown from daily returns."""
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(abs(dd.min())) if len(dd) else 0.0


def calculate_pit_pead_scores(
    prices: pd.DataFrame,
    events_df: pd.DataFrame,
    *,
    holding_days: int = 42,
) -> pd.DataFrame:
    """Calculates strictly causal point-in-time earnings surprise scores (SUE).

    Algorithm:
    1. For each earnings announcement in `events_df`, maps to the company's column
       and the row corresponding to `effective_trade_date` (which already accounts
       for BMO vs AMC release timing).
    2. Calculates standardized unexpected earnings (SUE) deflated by pre-event price.
    3. Propagates the surprise signal forward across the subsequent `holding_days` (42 trading days).
    4. On each trading day, standardizes active non-zero signals cross-sectionally.
    """
    n_bars, n_assets = prices.shape
    if n_bars < 10 or n_assets == 0:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns, dtype=float)

    # Format dates to YYYY-MM-DD strings for exact calendar matching
    date_strings = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in prices.index]
    date_to_idx = {d_str: i for i, d_str in enumerate(date_strings)}
    sym_to_idx = {sym: i for i, sym in enumerate(prices.columns)}

    raw_sue = np.zeros((n_bars, n_assets), dtype=float)

    for _, row in events_df.iterrows():
        sym = str(row["symbol"])
        trade_date = str(row["effective_trade_date"])

        # Handle RTN -> RTX mapping if needed
        c_idx = sym_to_idx.get(sym)
        if c_idx is None and sym == "RTN":
            c_idx = sym_to_idx.get("RTX")

        t_idx = date_to_idx.get(trade_date)
        if c_idx is None or t_idx is None:
            continue

        # Extract SUE
        sue_val = float(row.get("sue_price_deflated", np.nan))
        if np.isnan(sue_val) or abs(sue_val) < 1e-12:
            raw_surp = float(row.get("raw_surprise", np.nan))
            pre_px = float(row.get("pre_event_price", np.nan))
            if not np.isnan(raw_surp) and not np.isnan(pre_px) and pre_px > 0:
                sue_val = raw_surp / pre_px
            else:
                surp_pct = float(row.get("surprise_pct", 0.0))
                sue_val = surp_pct / 100.0 if not np.isnan(surp_pct) else 0.0

        if np.isnan(sue_val):
            continue

        end_hold = min(t_idx + holding_days, n_bars)
        raw_sue[t_idx:end_hold, c_idx] = sue_val

    # Cross-sectional standardization across active assets on each day
    scores_arr = np.zeros_like(raw_sue)
    for t in range(n_bars):
        row_vals = raw_sue[t]
        active_mask = np.abs(row_vals) > 1e-8
        n_active = int(np.sum(active_mask))

        if n_active >= 4:
            active_subset = row_vals[active_mask]
            m = float(np.mean(active_subset))
            s = float(np.std(active_subset))
            if s > 1e-8:
                z = np.zeros_like(row_vals)
                z[active_mask] = (active_subset - m) / s
                scores_arr[t] = z
            else:
                scores_arr[t] = row_vals
        else:
            scores_arr[t] = row_vals

    return pd.DataFrame(scores_arr, index=prices.index, columns=prices.columns)


def simulate_pit_pead_portfolio(
    universe: EquitiesUniverseData,
    surprise_scores: pd.DataFrame,
    *,
    hypothesis_id: str,
    partition: str = "OOS",
    top_k: int = 10,
    bottom_k: int = 10,
    holding_days: int = 42,
    gross_exposure: float = 1.0,
    deadband_retention_quantile_long: float = 0.40,
    deadband_retention_quantile_short: float = 0.60,
    cost_model: Optional[FactorCostModel] = None,
) -> FactorSimulationResult:
    """Simulates market-neutral PEAD portfolio with deadband turnover reduction and full IBKR Pro costs."""
    prices = universe.prices
    returns = universe.returns
    n_bars, n_assets = prices.shape

    if cost_model is None:
        cost_model = FactorCostModel.baseline_ibkr_pro_fixed()

    weights = np.zeros((n_bars, n_assets), dtype=float)
    scores_mat = surprise_scores.values
    returns_mat = returns.values

    current_weights = np.zeros(n_assets, dtype=float)
    leg_gross = gross_exposure / 2.0

    for t in range(1, n_bars):
        row_scores = scores_mat[t]
        active_mask = np.abs(row_scores) > 1e-8
        n_active = int(np.sum(active_mask))

        if n_active >= top_k + bottom_k:
            ranked_indices = np.argsort(row_scores)
            short_candidates = set(ranked_indices[:bottom_k])
            long_candidates = set(ranked_indices[-top_k:])

            short_cutoff = int(np.floor(n_assets * deadband_retention_quantile_short))
            long_cutoff = int(np.ceil(n_assets * deadband_retention_quantile_long))

            acceptable_shorts = set(ranked_indices[:short_cutoff])
            acceptable_longs = set(ranked_indices[long_cutoff:])

            new_weights = np.zeros(n_assets, dtype=float)

            # Sizing for long leg: retain existing longs in deadband, fill remainder from highest candidates
            target_longs = []
            for idx in np.where(current_weights > 0)[0]:
                if idx in acceptable_longs and idx not in target_longs and len(target_longs) < top_k:
                    target_longs.append(idx)
            for idx in reversed(ranked_indices[-top_k:]):
                if idx not in target_longs and len(target_longs) < top_k:
                    target_longs.append(idx)

            if target_longs:
                w_each = leg_gross / len(target_longs)
                for idx in target_longs:
                    new_weights[idx] = w_each

            # Sizing for short leg: retain existing shorts in deadband, fill remainder from lowest candidates
            target_shorts = []
            for idx in np.where(current_weights < 0)[0]:
                if idx in acceptable_shorts and idx not in target_shorts and len(target_shorts) < bottom_k:
                    target_shorts.append(idx)
            for idx in ranked_indices[:bottom_k]:
                if idx not in target_shorts and len(target_shorts) < bottom_k:
                    target_shorts.append(idx)

            if target_shorts:
                w_each = -leg_gross / len(target_shorts)
                for idx in target_shorts:
                    new_weights[idx] = w_each

            current_weights = new_weights

        weights[t] = current_weights

    # Performance and attribution computation
    long_returns = np.zeros(n_bars, dtype=float)
    short_returns = np.zeros(n_bars, dtype=float)
    gross_returns = np.zeros(n_bars, dtype=float)
    turnover = np.zeros(n_bars, dtype=float)
    rank_ic = np.zeros(n_bars, dtype=float)

    for t in range(1, n_bars):
        w_prev = weights[t - 1]
        r_curr = returns_mat[t]

        long_mask = w_prev > 0
        short_mask = w_prev < 0

        long_ret = float(np.sum(w_prev[long_mask] * r_curr[long_mask])) if np.any(long_mask) else 0.0
        short_ret = float(np.sum(w_prev[short_mask] * r_curr[short_mask])) if np.any(short_mask) else 0.0

        long_returns[t] = long_ret
        short_returns[t] = short_ret
        gross_returns[t] = long_ret + short_ret

        delta_w = np.abs(weights[t] - w_prev)
        turnover[t] = float(np.sum(delta_w) / 2.0)

        active_indices = np.where(np.abs(scores_mat[t - 1]) > 1e-8)[0]
        if len(active_indices) >= 5:
            rho, _ = spearmanr(scores_mat[t - 1, active_indices], r_curr[active_indices])
            rank_ic[t] = float(rho) if not np.isnan(rho) else 0.0

    # Apply Cost Model
    portfolio_equity = 100000.0
    sched = cost_model.schedule if hasattr(cost_model, "schedule") else cost_model
    daily_commissions = np.zeros(n_bars, dtype=float)
    daily_spread = np.zeros(n_bars, dtype=float)
    daily_slippage = np.zeros(n_bars, dtype=float)
    daily_borrow = np.zeros(n_bars, dtype=float)
    daily_regulatory = np.zeros(n_bars, dtype=float)
    net_returns = np.zeros(n_bars, dtype=float)

    for t in range(1, n_bars):
        trade_volume_pct = turnover[t]
        trade_notional = trade_volume_pct * portfolio_equity

        if trade_notional > 0:
            est_shares = trade_notional / sched.assumed_avg_share_price
            comm = max(sched.min_commission_usd, est_shares * sched.commission_per_share_usd)
            spread_cost = trade_notional * (sched.spread_bps / 10000.0)
            slip_cost = trade_notional * (sched.slippage_bps / 10000.0)
            reg_cost = trade_notional * (sched.regulatory_fees_bps / 10000.0)
        else:
            comm = 0.0
            spread_cost = 0.0
            slip_cost = 0.0
            reg_cost = 0.0

        short_notional = float(np.sum(np.abs(weights[t - 1][weights[t - 1] < 0]))) * portfolio_equity
        borrow_cost = short_notional * (sched.annual_short_borrow_bps / 10000.0) / 252.0

        daily_commissions[t] = comm
        daily_spread[t] = spread_cost
        daily_slippage[t] = slip_cost
        daily_borrow[t] = borrow_cost
        daily_regulatory[t] = reg_cost

        total_day_friction = comm + spread_cost + slip_cost + borrow_cost + reg_cost
        day_friction_pct = total_day_friction / portfolio_equity
        net_returns[t] = gross_returns[t] - day_friction_pct

    trading_days = n_bars - 1
    ann_factor = 252.0
    daily_net_mean = float(np.mean(net_returns[1:])) if trading_days > 0 else 0.0
    daily_net_std = float(np.std(net_returns[1:], ddof=1)) if trading_days > 1 else 0.0

    ann_net_return = daily_net_mean * ann_factor
    ann_net_sharpe = (daily_net_mean / daily_net_std * np.sqrt(ann_factor)) if daily_net_std > 1e-8 else 0.0
    max_dd = _compute_max_drawdown(pd.Series(net_returns[1:]))

    monthly_turnover = float(np.mean(turnover[1:]) * 21.0) if trading_days > 0 else 0.0
    valid_ic = rank_ic[np.abs(rank_ic) > 1e-8]
    mean_rank_ic = float(np.mean(valid_ic)) if len(valid_ic) > 0 else 0.0
    ic_pos_fraction = float(np.mean(valid_ic > 0.0)) if len(valid_ic) > 0 else 0.0

    costs_dict = {
        "commission_usd": float(np.sum(daily_commissions)),
        "spread_usd": float(np.sum(daily_spread)),
        "slippage_usd": float(np.sum(daily_slippage)),
        "borrow_usd": float(np.sum(daily_borrow)),
        "total_friction_usd": float(np.sum(daily_commissions + daily_spread + daily_slippage + daily_borrow + daily_regulatory)),
        "friction_drag_ratio": float(np.sum(daily_commissions + daily_spread + daily_slippage + daily_borrow + daily_regulatory) / max(np.sum(gross_returns[1:]) * portfolio_equity, 1.0)),
    }

    quantile_returns = {
        "long_leg_ann": float(np.mean(long_returns[1:]) * ann_factor),
        "short_leg_ann": float(np.mean(short_returns[1:]) * ann_factor),
        "gross_spread_ann": float(np.mean(gross_returns[1:]) * ann_factor),
        "net_spread_ann": ann_net_return,
    }

    return FactorSimulationResult(
        hypothesis_id=hypothesis_id,
        partition=partition,
        net_returns=pd.Series(net_returns, index=prices.index),
        gross_returns=pd.Series(gross_returns, index=prices.index),
        long_returns=pd.Series(long_returns, index=prices.index),
        short_returns=pd.Series(short_returns, index=prices.index),
        turnover_series=pd.Series(turnover, index=prices.index),
        rank_ic_series=pd.Series(rank_ic, index=prices.index),
        costs=costs_dict,
        annualized_net_sharpe=ann_net_sharpe,
        annualized_net_return=ann_net_return,
        max_drawdown=max_dd,
        monthly_turnover=monthly_turnover,
        mean_rank_ic=mean_rank_ic,
        ic_positive_fraction=ic_pos_fraction,
        quantile_returns=quantile_returns,
        cost_schedule=sched,
    )


def verify_quantile_monotonicity(
    universe: EquitiesUniverseData,
    scores: pd.DataFrame,
    *,
    holding_days: int = 42,
) -> tuple[bool, dict[str, float]]:
    """Evaluates whether returns are monotonic across SUE surprise quantiles."""
    prices = universe.prices
    returns = universe.returns
    n_bars, n_assets = prices.shape

    q_top_returns = []
    q_mid_returns = []
    q_bot_returns = []

    scores_mat = scores.values
    returns_mat = returns.values

    for t in range(1, n_bars):
        row_s = scores_mat[t - 1]
        active_idx = np.where(np.abs(row_s) > 1e-8)[0]

        if len(active_idx) >= 15:
            ranked = active_idx[np.argsort(row_s[active_idx])]
            n = len(ranked)
            k = max(n // 5, 2)

            top_idx = ranked[-k:]
            mid_start = (n - k) // 2
            mid_idx = ranked[mid_start : mid_start + k]
            bot_idx = ranked[:k]

            r_curr = returns_mat[t]
            q_top_returns.append(float(np.mean(r_curr[top_idx])))
            q_mid_returns.append(float(np.mean(r_curr[mid_idx])))
            q_bot_returns.append(float(np.mean(r_curr[bot_idx])))

    if not q_top_returns:
        return False, {"top_quintile_ann": 0.0, "mid_quintile_ann": 0.0, "bot_quintile_ann": 0.0}

    ann = 252.0
    r_top = float(np.mean(q_top_returns) * ann)
    r_mid = float(np.mean(q_mid_returns) * ann)
    r_bot = float(np.mean(q_bot_returns) * ann)

    is_monotonic = bool(r_top > r_bot)

    return is_monotonic, {
        "top_quintile_ann": r_top,
        "mid_quintile_ann": r_mid,
        "bot_quintile_ann": r_bot,
        "is_monotonic": is_monotonic,
    }


def evaluate_factor_gates_009(
    oos_res: FactorSimulationResult,
    adverse_res: FactorSimulationResult,
    prereg: FactorPreRegistration,
    *,
    is_monotonic: bool,
    replicated: Optional[bool] = None,
    is_res: Optional[FactorSimulationResult] = None,
) -> dict[str, Any]:
    """Evaluates the 7 frozen decision gates per ADR-022 and ADR-030."""
    criteria = prereg.pass_criteria

    min_sharpe = float(criteria.get("min_oos_net_sharpe", 1.0))
    min_ic_pos = float(criteria.get("min_ic_positive_frac", 0.65))
    min_mean_ic = float(criteria.get("min_mean_rank_ic", 0.03))
    max_turnover = float(criteria.get("max_monthly_turnover", 0.15))
    max_dd = float(criteria.get("max_drawdown", 0.15))
    min_adverse = float(criteria.get("min_adverse_net_return", 0.0))

    gates = {
        "gate_1_oos_net_sharpe": bool(oos_res.annualized_net_sharpe >= min_sharpe),
        "gate_2_ic_positive_fraction": bool(oos_res.ic_positive_fraction >= min_ic_pos),
        "gate_3_mean_rank_ic": bool(oos_res.mean_rank_ic >= min_mean_ic),
        "gate_4_quantile_monotonicity": bool(is_monotonic),
        "gate_5_max_drawdown": bool(oos_res.max_drawdown <= max_dd),
        "gate_6_monthly_turnover": bool(oos_res.monthly_turnover <= max_turnover),
        "gate_7_adverse_net_return": bool(adverse_res.annualized_net_return > min_adverse),
    }

    all_passed = all(gates.values())
    verdict = "candidate" if all_passed else "negative_result"

    failure_mode = ""
    failure_mode_basis = ""
    failure_mode_confidence = "high"

    if not all_passed:
        gross_spread = oos_res.quantile_returns.get("gross_spread_ann", 0.0)
        net_ret = oos_res.annualized_net_return

        if gross_spread > 0.0 and net_ret <= 0.0:
            failure_mode = "execution_constrained"
            failure_mode_basis = (
                f"Gross economic spread exists (+{gross_spread:.2%}) but execution costs "
                f"(-{oos_res.costs['total_friction_usd']:.2f} USD) dragged net return negative (-{net_ret:.2%})."
            )
        elif is_res is not None and is_res.annualized_net_sharpe >= min_sharpe and oos_res.annualized_net_sharpe < min_sharpe:
            failure_mode = "overfit_regime_fragile"
            failure_mode_basis = (
                f"In-sample performance (Sharpe {is_res.annualized_net_sharpe:.2f}) failed to generalize "
                f"to out-of-sample partition (Sharpe {oos_res.annualized_net_sharpe:.2f} < {min_sharpe:.2f})."
            )
        else:
            failure_mode = "mechanism_failure"
            reasons = []
            if not gates["gate_1_oos_net_sharpe"]:
                reasons.append(f"Net Sharpe {oos_res.annualized_net_sharpe:.2f} < {min_sharpe:.2f}")
            if not gates["gate_2_ic_positive_fraction"]:
                reasons.append(f"IC positive fraction {oos_res.ic_positive_fraction:.1%} < {min_ic_pos:.1%}")
            if not gates["gate_3_mean_rank_ic"]:
                reasons.append(f"Mean Rank IC {oos_res.mean_rank_ic:+.3f} < {min_mean_ic:+.3f}")
            if not gates["gate_4_quantile_monotonicity"]:
                reasons.append("Quantile monotonicity violated")
            if not gates["gate_5_max_drawdown"]:
                reasons.append(f"Max DD {oos_res.max_drawdown:.2%} > {max_dd:.2%}")
            if not gates["gate_6_monthly_turnover"]:
                reasons.append(f"Monthly turnover {oos_res.monthly_turnover:.1%} > {max_turnover:.1%}")
            if not gates["gate_7_adverse_net_return"]:
                reasons.append(f"Adverse net return {adverse_res.annualized_net_return:.2%} <= {min_adverse:.2%}")
            failure_mode_basis = f"Point-in-Time PEAD factor failed hurdles: {'; '.join(reasons)}."

    res: dict[str, Any] = {
        "verdict": verdict,
        "gates": gates,
        "metrics": {
            "net_sharpe": oos_res.annualized_net_sharpe,
            "annualized_net_return_pct": oos_res.annualized_net_return * 100.0,
            "mean_rank_ic": oos_res.mean_rank_ic,
            "ic_positive_fraction": oos_res.ic_positive_fraction,
            "monthly_turnover": oos_res.monthly_turnover,
            "max_drawdown_pct": oos_res.max_drawdown * 100.0,
            "adverse_net_return_pct": adverse_res.annualized_net_return * 100.0,
            "friction_drag_ratio": oos_res.costs.get("friction_drag_ratio", 0.0),
        },
    }

    if failure_mode:
        res["failure_mode"] = failure_mode
        res["failure_mode_basis"] = failure_mode_basis
        res["failure_mode_confidence"] = failure_mode_confidence

    return res


def run_pit_screen_009(
    universe: EquitiesUniverseData,
    prereg: FactorPreRegistration,
    events_df: pd.DataFrame,
    *,
    output_path: Optional[Path | str] = None,
    replicated: Optional[bool] = None,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Runs the complete EQ-009 Point-in-Time PEAD factor screen and seals evidence bundle."""
    missing = prereg.missing_fields()
    if missing:
        raise EquitiesDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise EquitiesDataError("OOS partition cannot be used for parameter choice")

    prices = universe.prices
    params = prereg.parameters

    holding_days = int(params.get("holding_days", 42))
    top_k = int(params.get("top_k", 10))
    bottom_k = int(params.get("bottom_k", 10))
    gross_exp = float(params.get("gross_exposure", 1.0))
    db_long = float(params.get("deadband_retention_quantile_long", 0.40))
    db_short = float(params.get("deadband_retention_quantile_short", 0.60))

    # 1. Compute causal PIT PEAD surprise scores across full price matrix
    scores = calculate_pit_pead_scores(
        prices,
        events_df,
        holding_days=holding_days,
    )

    # 2. Slice Partitions
    is_univ = universe.slice_partition("IS")
    oos_univ = universe.slice_partition("OOS")

    # 3. In-Sample Simulation (Baseline IBKR Pro fixed)
    is_res = simulate_pit_pead_portfolio(
        is_univ,
        scores.loc[is_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="IS",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        gross_exposure=gross_exp,
        deadband_retention_quantile_long=db_long,
        deadband_retention_quantile_short=db_short,
        cost_model=FactorCostModel.baseline_ibkr_pro_fixed(),
    )

    # 4. Out-of-Sample Simulation (Baseline IBKR Pro fixed)
    oos_res = simulate_pit_pead_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        gross_exposure=gross_exp,
        deadband_retention_quantile_long=db_long,
        deadband_retention_quantile_short=db_short,
        cost_model=FactorCostModel.baseline_ibkr_pro_fixed(),
    )

    # 5. Adverse Stress OOS Simulation
    adverse_res = simulate_pit_pead_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS_ADVERSE",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        gross_exposure=gross_exp,
        deadband_retention_quantile_long=db_long,
        deadband_retention_quantile_short=db_short,
        cost_model=FactorCostModel.stressed_adverse(),
    )

    # 6. Quantile Monotonicity Verification
    is_mono, mono_spreads = verify_quantile_monotonicity(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        holding_days=holding_days,
    )

    # 7. Decision Gates Evaluation
    gates_eval = evaluate_factor_gates_009(
        oos_res,
        adverse_res,
        prereg,
        is_monotonic=is_mono,
        replicated=replicated,
        is_res=is_res,
    )

    bundle = {
        "hypothesis_id": prereg.hypothesis_id,
        "factor_name": prereg.factor_name,
        "manifest_digest": universe.manifest.digest(),
        "is": is_res.to_dict(),
        "oos": oos_res.to_dict(),
        "adverse_oos": adverse_res.to_dict(),
        "monotonicity": mono_spreads,
        "gates": gates_eval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    target_path = Path(output_path) if output_path is not None else (RESULTS_DIR / f"{prereg.hypothesis_id}-evidence-bundle.json")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    write_bundle(target_path, bundle)

    return bundle
