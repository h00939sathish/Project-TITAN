"""EQ-008: Broad Universe Staggered Post-Earnings Announcement Drift (PEAD) Factor Screen.

Research-only. Evaluates point-in-time staggered earnings surprise signals across a 50-stock
liquid US equity universe, staggered 42-day drift holding horizons, turnover-suppressed
portfolio execution (<= 8.0%-10.0%/month), and explicit IBKR Pro friction attribution
per ADR-029, ADR-030, and ADR-031 governance standards.

Preserves deterministic boundaries: zero execution/broker/runtime imports.
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
)
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseData,
    EquitiesUniverseManifest,
)
from titan.research.factors import cross_sectional_zscore

_REPO_ROOT = Path(__file__).resolve().parents[3]
HYP_DIR = _REPO_ROOT / "research" / "equities" / "hypotheses"
RESULTS_DIR = _REPO_ROOT / "research" / "equities" / "results"


@dataclass(frozen=True)
class FactorPreRegistration:
    """Immutable pre-registration parameters for EQ-008."""

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


def _compute_max_drawdown(returns: pd.Series) -> float:
    """Computes peak-to-trough maximum drawdown from daily returns."""
    cum = (1.0 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return float(abs(dd.min())) if len(dd) else 0.0


def calculate_staggered_pead_scores(
    prices: pd.DataFrame,
    *,
    benchmark_col: str | None = None,
    event_freq_days: int = 63,
    vol_window: int = 63,
    holding_days: int = 42,
    n_cohorts: int = 10,
) -> pd.DataFrame:
    """Calculates point-in-time standardized earnings surprise jumps across a staggered schedule.

    Algorithm:
    1. For each asset i in the universe, assigns a deterministic quarterly announcement cadence
       grouped into `n_cohorts` staggered cohorts offset across the quarterly earnings cycle.
    2. On each cohort's event date, measures the 1-day abnormal event return relative to benchmark/market.
    3. Normalizes event jump by pre-event rolling idiosyncratic volatility (lagged 1 day to strictly avoid lookahead).
    4. Propagates the surprise signal across the subsequent `holding_days` (e.g. 42 trading days).
    5. Applies cross-sectional standardization across universe assets at each date.
    """
    n_bars, n_assets = prices.shape
    if n_bars < vol_window + 10 or n_assets == 0:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns, dtype=float)

    price_vals = prices.values
    daily_returns = np.zeros_like(price_vals)
    daily_returns[1:] = (price_vals[1:] - price_vals[:-1]) / np.where(
        price_vals[:-1] != 0, price_vals[:-1], np.nan
    )
    daily_returns = np.nan_to_num(daily_returns, nan=0.0)

    if benchmark_col is not None and benchmark_col in prices.columns:
        b_idx = prices.columns.get_loc(benchmark_col)
        mkt_ret = daily_returns[:, b_idx]
    else:
        mkt_ret = np.mean(daily_returns, axis=1)

    # Rolling pre-event volatility (shifted by 1 bar to strictly avoid lookahead on event day)
    ret_df = pd.DataFrame(daily_returns, index=prices.index)
    rolling_vol = (
        ret_df.rolling(vol_window).std().replace(0.0, np.nan).shift(1).values
    )

    raw_sue = np.zeros((n_bars, n_assets), dtype=float)
    warmup = max(vol_window, event_freq_days)
    cohort_size = max(n_assets // n_cohorts, 1)
    offset_step = event_freq_days // n_cohorts

    for c in range(n_cohorts):
        c_start = c * cohort_size
        c_end = (c + 1) * cohort_size if c < n_cohorts - 1 else n_assets
        offset = c * offset_step
        event_indices = list(range(warmup + offset, n_bars, event_freq_days))

        for ev_idx in event_indices:
            for i in range(c_start, c_end):
                p_t = price_vals[ev_idx, i]
                p_prev = price_vals[ev_idx - 1, i]
                if p_prev <= 0.0 or np.isnan(p_t) or np.isnan(p_prev):
                    continue

                raw_ret = (p_t - p_prev) / p_prev
                abnormal_ret = raw_ret - mkt_ret[ev_idx]

                vol_val = rolling_vol[ev_idx, i]
                if np.isnan(vol_val) or vol_val <= 1e-8:
                    vol_val = 0.015

                sue_val = abnormal_ret / vol_val

                end_hold_idx = min(ev_idx + holding_days, n_bars)
                raw_sue[ev_idx:end_hold_idx, i] = sue_val

    # Normalize active signals on each day
    scores_arr = np.zeros_like(raw_sue)
    for t_idx in range(warmup, n_bars):
        row = raw_sue[t_idx]
        active_mask = np.abs(row) > 1e-8
        if np.sum(active_mask) >= 4:
            active_vals = row[active_mask]
            m = float(np.mean(active_vals))
            s = float(np.std(active_vals))
            if s > 1e-8:
                z = np.zeros_like(row)
                z[active_mask] = (active_vals - m) / s
                scores_arr[t_idx] = z
            else:
                scores_arr[t_idx] = row
        else:
            scores_arr[t_idx] = row

    return pd.DataFrame(scores_arr, index=prices.index, columns=prices.columns)


def simulate_staggered_pead_portfolio(
    universe: EquitiesUniverseData,
    surprise_scores: pd.DataFrame,
    *,
    hypothesis_id: str,
    partition: str = "OOS",
    top_k: int = 10,
    bottom_k: int = 10,
    holding_days: int = 42,
    event_freq_days: int = 63,
    n_cohorts: int = 10,
    gross_exposure: float = 1.0,
    cost_model: VenueCostSchedule | None = None,
    deadband_retention_quantile_long: float = 0.25,
    deadband_retention_quantile_short: float = 0.75,
) -> FactorSimulationResult:
    """Simulates a dollar-neutral PEAD long/short factor portfolio with staggered rebalancing.

    Execution Invariants:
    - Target: +50% Long across 10 staggered cohorts, -50% Short across 10 staggered cohorts.
    - Zero net dollar exposure; 1.0 gross exposure.
    - Strict t+1 causal execution (weights decided at day t applied to returns on day t+1).
    - Staggered holding horizon with deadband retention suppresses monthly turnover to <= 8.0%-10.0%/month.
    - Full friction accounting per ADR-031 (commissions, 1 bps spread, 0.5 bps slippage, 50 bps short borrow).
    """
    cost = cost_model or VenueCostSchedule.standard_us_equity()
    prices = universe.prices
    returns = universe.returns

    common_index = prices.index.intersection(surprise_scores.index)
    prices = prices.loc[common_index]
    returns = returns.loc[common_index]
    scores = surprise_scores.loc[common_index]

    n_bars, n_assets = prices.shape
    if n_bars < holding_days + 5:
        raise ValueError("insufficient data points to simulate staggered PEAD factor portfolio")

    daily_weights = pd.DataFrame(0.0, index=common_index, columns=prices.columns, dtype=float)
    cohort_size = max(n_assets // n_cohorts, 1)
    offset_step = event_freq_days // n_cohorts

    long_weight_per_slot = (gross_exposure / 2.0) / float(top_k)
    short_weight_per_slot = (gross_exposure / 2.0) / float(bottom_k)
    slots_per_cohort_long = max(top_k // n_cohorts, 1)
    slots_per_cohort_short = max(bottom_k // n_cohorts, 1)

    # Track current active positions per cohort
    cohort_longs: dict[int, list[str]] = {c: [] for c in range(n_cohorts)}
    cohort_shorts: dict[int, list[str]] = {c: [] for c in range(n_cohorts)}

    # Build cohort rebalance schedules
    rebal_events: dict[int, list[int]] = {}  # t_idx -> list of cohort indices rebalancing
    for c in range(n_cohorts):
        offset = c * offset_step
        indices = list(range(offset, n_bars, event_freq_days))
        for idx in indices:
            if idx not in rebal_events:
                rebal_events[idx] = []
            rebal_events[idx].append(c)

    for t_idx, d in enumerate(common_index):
        # Check if any cohort rebalances on day t_idx
        if t_idx in rebal_events:
            for c in rebal_events[t_idx]:
                c_start = c * cohort_size
                c_end = (c + 1) * cohort_size if c < n_cohorts - 1 else n_assets
                c_syms = prices.columns[c_start:c_end].tolist()

                # Evaluate scores of cohort assets on rebalance day
                day_scores = scores.iloc[t_idx][c_syms].dropna()
                if len(day_scores) < slots_per_cohort_long + slots_per_cohort_short:
                    continue

                ranks = day_scores.rank(ascending=True)
                pct_ranks = (ranks - 1.0) / max(len(day_scores) - 1.0, 1.0)

                # Deadband long retention
                retained_longs = [
                    s for s in cohort_longs[c]
                    if s in pct_ranks.index and pct_ranks[s] >= deadband_retention_quantile_long
                ]
                if len(retained_longs) < slots_per_cohort_long:
                    cands = [s for s in day_scores.sort_values(ascending=False).index if s not in retained_longs]
                    retained_longs.extend(cands[: slots_per_cohort_long - len(retained_longs)])
                cohort_longs[c] = retained_longs[:slots_per_cohort_long]

                # Deadband short retention
                retained_shorts = [
                    s for s in cohort_shorts[c]
                    if s in pct_ranks.index and pct_ranks[s] <= deadband_retention_quantile_short
                ]
                if len(retained_shorts) < slots_per_cohort_short:
                    cands = [s for s in day_scores.sort_values(ascending=True).index if s not in retained_shorts]
                    retained_shorts.extend(cands[: slots_per_cohort_short - len(retained_shorts)])
                cohort_shorts[c] = retained_shorts[:slots_per_cohort_short]

        # Construct current weights vector
        w = pd.Series(0.0, index=prices.columns)
        for c in range(n_cohorts):
            for s in cohort_longs[c]:
                w[s] += long_weight_per_slot
            for s in cohort_shorts[c]:
                w[s] -= short_weight_per_slot

        daily_weights.iloc[t_idx] = w

    # Strictly causal execution: Shift weights by 1 day (decision at t, executed at t+1)
    held_weights = daily_weights.shift(1).fillna(0.0)

    # Returns decomposition
    long_w = held_weights.clip(lower=0.0)
    short_w = held_weights.clip(upper=0.0)

    long_daily = (long_w * returns).sum(axis=1)
    short_daily = (short_w * returns).sum(axis=1)
    gross_daily = long_daily + short_daily

    # Friction & Costs attribution per ADR-031
    # 1. Short borrow fee: accrued daily on short leg
    daily_borrow_rate = (cost.annual_short_borrow_bps * 1e-4) / 252.0
    borrow_costs = short_w.abs().sum(axis=1) * daily_borrow_rate

    # 2. Turnover friction (commissions, bid-ask spread, slippage, regulatory fees)
    delta_w = daily_weights.diff().abs().sum(axis=1).fillna(0.0)
    comm_rate = cost.commission_per_share_usd / cost.assumed_avg_share_price
    commission_costs = delta_w * comm_rate
    spread_costs = delta_w * (cost.spread_bps * 1e-4)
    slippage_costs = delta_w * (cost.slippage_bps * 1e-4)
    regulatory_costs = delta_w * (cost.regulatory_fees_bps * 1e-4)

    total_friction = borrow_costs + commission_costs + spread_costs + slippage_costs + regulatory_costs
    net_daily = gross_daily - total_friction

    # Performance metrics
    mean_net = float(net_daily.mean())
    std_net = float(net_daily.std())
    ann_sharpe = (mean_net / std_net * np.sqrt(252.0)) if std_net > 0 else 0.0
    ann_return = mean_net * 252.0
    max_dd = _compute_max_drawdown(net_daily)

    # Monthly turnover (one-sided canonical turnover: 0.5 * sum(abs(delta_w)) / months)
    monthly_turnover = float(0.5 * delta_w.sum() / max(n_bars / 21.0, 1.0))

    # Rank Information Coefficient (IC) across forward holding window
    fwd_holding_returns = prices.pct_change(holding_days).shift(-holding_days)
    ic_values: list[float] = []

    # Sample IC across weekly dates
    sample_dates = common_index[::5]

    for s_date in sample_dates:
        if s_date not in fwd_holding_returns.index:
            continue
        f_slice = scores.loc[s_date].dropna()
        active_f = f_slice[f_slice.abs() > 1e-8]
        r_slice = fwd_holding_returns.loc[s_date].dropna()
        common_syms = active_f.index.intersection(r_slice.index)

        if len(common_syms) >= 8:
            f_vals = active_f[common_syms]
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
    surprise_scores: pd.DataFrame,
    *,
    holding_days: int = 42,
    num_quantiles: int = 5,
) -> tuple[bool, dict[str, float]]:
    """Calculates forward holding returns across quintiles (Q5 Top to Q1 Bottom)."""
    prices = universe.prices
    common_index = prices.index.intersection(surprise_scores.index)
    scores = surprise_scores.loc[common_index]
    prices = prices.loc[common_index]

    fwd_returns = prices.pct_change(holding_days).shift(-holding_days)

    sample_dates = common_index[::5]
    quantile_accum: dict[int, list[float]] = {q: [] for q in range(1, num_quantiles + 1)}

    for d in sample_dates:
        if d not in fwd_returns.index:
            continue
        day_scores = scores.loc[d].dropna()
        active_scores = day_scores[day_scores.abs() > 1e-8]
        if len(active_scores) < num_quantiles * 2:
            continue

        fwd_slice = fwd_returns.loc[d].dropna()
        common_syms = active_scores.index.intersection(fwd_slice.index)
        if len(common_syms) < num_quantiles * 2:
            continue

        ranked = active_scores[common_syms].rank(ascending=True)
        q_bins = pd.qcut(ranked, q=num_quantiles, labels=list(range(1, num_quantiles + 1)), duplicates="drop")

        for q in range(1, num_quantiles + 1):
            q_syms = q_bins[q_bins == q].index
            if len(q_syms) > 0:
                ret = float(fwd_slice[q_syms].mean())
                if not np.isnan(ret):
                    quantile_accum[q].append(ret)

    ann_factor = 252.0 / float(holding_days)
    avg_quantiles = {}
    for q in range(1, num_quantiles + 1):
        vals = quantile_accum[q]
        avg_quantiles[f"Q{q}_ann"] = round(float(np.mean(vals) * ann_factor), 4) if vals else 0.0

    q_top = avg_quantiles.get(f"Q{num_quantiles}_ann", 0.0)
    q_mid = avg_quantiles.get(f"Q{(num_quantiles + 1) // 2}_ann", 0.0)
    q_bot = avg_quantiles.get("Q1_ann", 0.0)

    # Monotonicity check: Top > Mid > Bottom or Top > Bottom
    is_monotonic = bool(q_top > q_mid > q_bot) or bool(q_top > q_bot and q_top >= q_mid >= q_bot)

    spreads = {
        "top_quantile_ann": q_top,
        "mid_quantile_ann": q_mid,
        "bot_quantile_ann": q_bot,
        "quintile_returns": avg_quantiles,
        "is_monotonic": is_monotonic,
    }
    return is_monotonic, spreads


def evaluate_factor_gates_008(
    oos_res: FactorSimulationResult,
    adverse_res: FactorSimulationResult,
    prereg: FactorPreRegistration,
    *,
    is_monotonic: bool = False,
    replicated: bool = False,
    is_res: FactorSimulationResult | None = None,
) -> dict[str, Any]:
    """Evaluates frozen decision gates for EQ-008 and classifies outcome per AGENTS.md Rule 8."""
    min_sharpe = float(prereg.pass_criteria.get("min_oos_net_sharpe", 1.0))
    min_ic_pos = float(prereg.pass_criteria.get("min_ic_positive_frac", 0.70))
    min_mean_ic = float(prereg.pass_criteria.get("min_mean_rank_ic", 0.05))
    max_turnover = float(prereg.pass_criteria.get("max_monthly_turnover", 0.12))
    target_turnover = float(prereg.pass_criteria.get("target_monthly_turnover", 0.10))
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
            if not gates["turnover_capacity"]:
                reasons.append(f"Monthly turnover {oos_res.monthly_turnover:.1%} > {max_turnover:.1%}")
            failure_mode_basis = (
                f"Staggered PEAD factor failed hurdles: {'; '.join(reasons)}."
            )
            disambiguation = "The staggered PEAD mechanism lacks sufficient cross-sectional predictive power."

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


def run_event_screen_008(
    universe: EquitiesUniverseData,
    prereg: FactorPreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Runs the complete EQ-008 Staggered PEAD event screen and saves evidence bundle to research/equities/results."""
    missing = prereg.missing_fields()
    if missing:
        raise EquitiesDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise EquitiesDataError("OOS partition cannot be used for parameter choice")

    prices = universe.prices
    params = prereg.parameters

    event_freq = int(params.get("event_frequency_days", 63))
    holding_days = int(params.get("holding_days", 42))
    vol_win = int(params.get("vol_window_days", 63))
    top_k = int(params.get("top_k", 10))
    bottom_k = int(params.get("bottom_k", 10))
    gross_exp = float(params.get("gross_exposure", 1.0))
    db_long = float(params.get("deadband_retention_quantile_long", 0.25))
    db_short = float(params.get("deadband_retention_quantile_short", 0.75))

    # 1. Compute point-in-time Staggered PEAD surprise scores across full price matrix
    scores = calculate_staggered_pead_scores(
        prices,
        event_freq_days=event_freq,
        vol_window=vol_win,
        holding_days=holding_days,
    )

    # 2. Slice Partitions
    is_univ = universe.slice_partition("IS")
    oos_univ = universe.slice_partition("OOS")

    # 3. In-Sample Simulation (Baseline IBKR Pro fixed)
    is_res = simulate_staggered_pead_portfolio(
        is_univ,
        scores.loc[is_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="IS",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        event_freq_days=event_freq,
        gross_exposure=gross_exp,
        deadband_retention_quantile_long=db_long,
        deadband_retention_quantile_short=db_short,
        cost_model=FactorCostModel.baseline_ibkr_pro_fixed(),
    )

    # 4. Out-of-Sample Simulation (Baseline IBKR Pro fixed)
    oos_res = simulate_staggered_pead_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        event_freq_days=event_freq,
        gross_exposure=gross_exp,
        deadband_retention_quantile_long=db_long,
        deadband_retention_quantile_short=db_short,
        cost_model=FactorCostModel.baseline_ibkr_pro_fixed(),
    )

    # 5. Adverse Stress OOS Simulation
    adverse_res = simulate_staggered_pead_portfolio(
        oos_univ,
        scores.loc[oos_univ.prices.index],
        hypothesis_id=prereg.hypothesis_id,
        partition="OOS_ADVERSE",
        top_k=top_k,
        bottom_k=bottom_k,
        holding_days=holding_days,
        event_freq_days=event_freq,
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
    gates_eval = evaluate_factor_gates_008(
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

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / f"{prereg.hypothesis_id}-evidence-bundle.json"
    out_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    return bundle
