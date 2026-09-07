"""EQ-Micro-001: ETF Constituent Intraday Lead-Lag & Basket Imbalance Factor Screen.

Research-only. Evaluates point-in-time intraday ETF lead-lag propagation across a 50-stock
liquid US equity universe, 5-minute bar frequency, 30-minute holding deadband, flat-at-close
liquidation, and explicit IBKR Pro friction attribution per ADR-029, ADR-030, and ADR-031 standards.

Preserves deterministic boundaries: zero execution/broker/runtime imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
from titan.data.equities_intraday import (
    EquitiesIntradayDataError,
    EquitiesIntradayManifest,
    EquitiesIntradayUniverseData,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
HYP_DIR = _REPO_ROOT / "research" / "equities" / "hypotheses"
RESULTS_DIR = _REPO_ROOT / "research" / "equities" / "results"
PREREG_PATH = HYP_DIR / "EQ-Micro-001-prereg.json"
MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_liquid_intraday_v1.json"


@dataclass(frozen=True)
class FactorPreRegistration:
    """Immutable pre-registration parameters for EQ-Micro-001."""

    hypothesis_id: str
    factor_name: str
    etf_anchors: list[str]
    parameters: dict[str, Any]
    cost_label: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    pass_criteria: dict[str, Any]
    universe_label: str = ""
    economic_rationale: str = ""
    limitations: str = ""

    def missing_fields(self) -> list[str]:
        missing = []
        for f in (
            "hypothesis_id",
            "factor_name",
            "etf_anchors",
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
            etf_anchors=list(data.get("etf_anchors", [])),
            parameters=dict(data.get("parameters", {})),
            cost_label=data.get("cost_label", ""),
            is_partition=dict(data.get("is_partition", {})),
            oos_partition=dict(data.get("oos_partition", {})),
            pass_criteria=dict(data.get("pass_criteria", {})),
            universe_label=data.get("universe_label", ""),
            economic_rationale=data.get("economic_rationale", ""),
            limitations=data.get("limitations", ""),
        )


def load_factor_preregistration(path: str | Path) -> FactorPreRegistration:
    """Loads and deserializes an immutable factor pre-registration file."""
    with open(path, encoding="utf-8") as fh:
        return FactorPreRegistration.from_dict(json.load(fh))


def _zscore_series(s: pd.Series) -> pd.Series:
    """Z-scores a 1D pandas Series across constituents."""
    std = float(s.std())
    if std > 0:
        return (s - s.mean()) / std
    return pd.Series(0.0, index=s.index)


def calculate_etf_intraday_lead_lag_signals(
    univ: EquitiesIntradayUniverseData,
    parameters: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Calculates point-in-time ETF-constituent lead-lag signals from 5-minute bars.

    Signal Mechanics:
    1. Measures 3-bar (15m) trailing ETF impulse on SPY/QQQ: r_etf = (P_t - P_{t-3}) / P_{t-3}.
    2. Filters for significant macro impulses where |r_etf| > 1.5 * rolling_std.
    3. Calculates single-stock constituent trailing returns: r_i = (P_{i,t} - P_{i,t-3}) / P_{i,t-3}.
    4. Residual divergence epsilon_i = r_i - r_etf.
    5. On upward ETF surge: laggards (epsilon_i < 0) are scored positively (Long).
       On downward ETF plunge: laggards (epsilon_i > 0) are scored negatively (Short).
    6. All signals are zeroed out at 15:55 ET to enforce flat-at-close intraday holding.
    """
    params = parameters or {}
    lookback = int(params.get("impulse_lookback_bars", 3))
    threshold_std = float(params.get("impulse_threshold_std", 1.5))
    flat_at_close = bool(params.get("flat_at_close", True))

    etf_prices = univ.etf_prices
    stock_prices = univ.stock_prices

    primary_etf = "SPY" if "SPY" in etf_prices.columns else etf_prices.columns[0]
    spy_p = etf_prices[primary_etf]

    # Trailing 3-bar returns
    spy_ret3 = (spy_p - spy_p.shift(lookback)) / spy_p.shift(lookback)
    spy_vol = spy_ret3.rolling(window=78, min_periods=20).std().shift(1)  # 1-day rolling volatility, lagged
    spy_impulse = spy_ret3 / spy_vol.replace(0.0, np.nan)

    stock_ret3 = (stock_prices - stock_prices.shift(lookback)) / stock_prices.shift(lookback)

    # Residual relative to ETF
    residual = stock_ret3.sub(spy_ret3, axis=0)

    # Cross-sectional z-score of residual
    scores = pd.DataFrame(0.0, index=stock_prices.index, columns=stock_prices.columns)

    for idx in stock_prices.index[lookback:]:
        imp = spy_impulse.loc[idx]
        if np.isnan(imp):
            continue

        if imp >= threshold_std:
            # Upward ETF impulse: Lagging stocks (negative residual) are scored positive
            res_row = residual.loc[idx].dropna()
            if len(res_row) > 10:
                raw_score = -res_row
                scores.loc[idx, res_row.index] = _zscore_series(raw_score)
        elif imp <= -threshold_std:
            # Downward ETF impulse: Lagging stocks (positive residual) are scored negative
            res_row = residual.loc[idx].dropna()
            if len(res_row) > 10:
                raw_score = -res_row
                scores.loc[idx, res_row.index] = _zscore_series(raw_score)

    if flat_at_close:
        # Zero out signal at end of each day (15:55 / final bars)
        for idx in scores.index:
            time_str = str(idx)
            if "15:55" in time_str or "16:00" in time_str:
                scores.loc[idx] = 0.0

    return scores.fillna(0.0)


def simulate_intraday_lead_lag_portfolio(
    univ: EquitiesIntradayUniverseData,
    scores: pd.DataFrame,
    cost_model: FactorCostModel,
    parameters: dict[str, Any] | None = None,
    partition: str = "OOS",
    hypothesis_id: str = "EQ-Micro-001",
) -> FactorSimulationResult:
    """Simulates an intraday dollar-neutral long/short portfolio with 30m holding deadbands."""
    params = parameters or {}
    top_k = int(params.get("top_k", 10))
    bottom_k = int(params.get("bottom_k", 10))
    holding_bars = int(params.get("holding_horizon_bars", 6))
    gross_exp = float(params.get("gross_exposure", 1.0))

    stock_prices = univ.stock_prices
    returns_matrix = univ.returns[stock_prices.columns]

    n_bars = len(stock_prices)
    n_assets = len(stock_prices.columns)
    weights = np.zeros((n_bars, n_assets), dtype=float)

    # Track active positions and bar age
    active_cohorts: list[dict[str, Any]] = []

    for t in range(n_bars):
        current_time = str(stock_prices.index[t])
        is_close_exit = "15:55" in current_time or "16:00" in current_time

        # Age active cohorts
        surviving_cohorts = []
        if not is_close_exit:
            for c in active_cohorts:
                c["bars_held"] += 1
                if c["bars_held"] < holding_bars:
                    surviving_cohorts.append(c)
        active_cohorts = surviving_cohorts

        # Form new cohort if active signal exists
        if not is_close_exit:
            row_scores = scores.iloc[t].values
            non_zeros = np.where(row_scores != 0.0)[0]
            if len(non_zeros) >= (top_k + bottom_k):
                sorted_idx = np.argsort(row_scores)
                long_idx = sorted_idx[-top_k:]
                short_idx = sorted_idx[:bottom_k]

                w = np.zeros(n_assets, dtype=float)
                w[long_idx] = (gross_exp / 2.0) / top_k
                w[short_idx] = -(gross_exp / 2.0) / bottom_k

                active_cohorts.append({"weights": w, "bars_held": 0})

        # Combine cohort weights
        if active_cohorts:
            combined_w = np.zeros(n_assets, dtype=float)
            for c in active_cohorts:
                combined_w += c["weights"]
            # Normalize to target gross exposure
            total_gross = np.sum(np.abs(combined_w))
            if total_gross > 0.0:
                combined_w = combined_w * (gross_exp / total_gross)
            weights[t] = combined_w
        else:
            weights[t] = 0.0

    # Calculate returns and turnover
    weights_df = pd.DataFrame(weights, index=stock_prices.index, columns=stock_prices.columns)
    lagged_w = weights_df.shift(1).fillna(0.0)

    long_w = lagged_w.clip(lower=0.0)
    short_w = (-lagged_w).clip(lower=0.0)

    long_returns = (long_w * returns_matrix).sum(axis=1)
    short_returns = (short_w * (-returns_matrix)).sum(axis=1)
    gross_returns = long_returns + short_returns

    turnover = (weights_df - lagged_w).abs().sum(axis=1)

    # Cost friction modeling (IBKR Pro $0.005/sh + $1 min per trade)
    friction_series = pd.Series(0.0, index=stock_prices.index)
    mean_asset_price = stock_prices.mean().mean()
    if mean_asset_price <= 0:
        mean_asset_price = 100.0

    portfolio_equity = 100000.0
    total_commission_dollars = 0.0
    total_spread_dollars = 0.0
    total_slippage_dollars = 0.0

    for idx, to in turnover.items():
        if to > 0.0:
            traded_notional = to * portfolio_equity
            num_trades = int(np.sum(np.abs(weights_df.loc[idx] - lagged_w.loc[idx]) > 0.0001))
            num_trades = max(1, num_trades)

            shares = traded_notional / mean_asset_price
            comm_per_order = max(cost_model.min_commission_usd, (shares / num_trades) * cost_model.commission_per_share_usd)
            total_comm = comm_per_order * num_trades

            spread_cost = traded_notional * (cost_model.spread_bps / 10000.0)
            slip_cost = traded_notional * (cost_model.slippage_bps / 10000.0)

            total_commission_dollars += total_comm
            total_spread_dollars += spread_cost
            total_slippage_dollars += slip_cost

            friction_dollars = total_comm + spread_cost + slip_cost
            friction_series.loc[idx] = friction_dollars / portfolio_equity

    net_returns = gross_returns - friction_series

    # Daily aggregation for standard annualized performance metrics
    daily_gross = gross_returns.resample("B").sum()
    daily_net = net_returns.resample("B").sum()
    daily_long = long_returns.resample("B").sum()
    daily_short = short_returns.resample("B").sum()
    daily_turnover = turnover.resample("B").sum()

    annual_factor = 252.0
    ann_net_ret = float(daily_net.mean() * annual_factor)
    ann_net_vol = float(daily_net.std() * np.sqrt(annual_factor))
    net_sharpe = (ann_net_ret / ann_net_vol) if ann_net_vol > 0 else 0.0

    cum_net = (1.0 + daily_net).cumprod()
    cum_max = cum_net.cummax()
    dd = (cum_max - cum_net) / cum_max
    max_dd = float(dd.max()) if len(dd) else 0.0

    # Monthly turnover = sum of daily turnovers across calendar month (~21 days)
    monthly_to = float(daily_turnover.mean() * 21.0)

    # Rank IC on 6-bar forward horizon
    mean_ic, pos_frac = compute_lead_lag_rank_ic(univ, scores, forward_bars=holding_bars)

    # Quantile Monotonicity
    total_long_ret = float(daily_long.sum())
    total_short_ret = float(daily_short.sum())
    monotonic = bool(total_long_ret > 0.0 and total_short_ret > 0.0)

    costs_dict = {
        "commission_usd": total_commission_dollars,
        "spread_usd": total_spread_dollars,
        "slippage_usd": total_slippage_dollars,
        "borrow_usd": 0.0,
        "total_friction_usd": total_commission_dollars + total_spread_dollars + total_slippage_dollars,
        "friction_drag_ratio": (total_commission_dollars + total_spread_dollars + total_slippage_dollars) / max(1.0, float(daily_gross.sum()) * portfolio_equity),
    }

    return FactorSimulationResult(
        hypothesis_id=hypothesis_id,
        partition=partition,
        net_returns=daily_net,
        gross_returns=daily_gross,
        long_returns=daily_long,
        short_returns=daily_short,
        turnover_series=daily_turnover,
        rank_ic_series=pd.Series([mean_ic], index=[daily_net.index[-1] if len(daily_net) else pd.Timestamp.now()]),
        costs=costs_dict,
        annualized_net_sharpe=net_sharpe,
        annualized_net_return=ann_net_ret,
        max_drawdown=max_dd,
        monthly_turnover=monthly_to,
        mean_rank_ic=mean_ic,
        ic_positive_fraction=pos_frac,
        quantile_returns={"long": total_long_ret, "short": total_short_ret, "monotonic": monotonic},
        cost_schedule=cost_model,
    )


def compute_lead_lag_rank_ic(
    univ: EquitiesIntradayUniverseData,
    scores: pd.DataFrame,
    forward_bars: int = 6,
) -> tuple[float, float]:
    """Computes cross-sectional Rank IC (Spearman rho) and positive IC fraction."""
    stock_prices = univ.stock_prices
    forward_returns = (stock_prices.shift(-forward_bars) - stock_prices) / stock_prices

    ic_list = []
    for idx in scores.index[:-forward_bars]:
        s_row = scores.loc[idx]
        if np.all(s_row == 0.0):
            continue

        r_row = forward_returns.loc[idx]
        valid = s_row.index[(s_row != 0.0) & (~r_row.isna())]
        if len(valid) >= 10:
            rho, _ = spearmanr(s_row[valid], r_row[valid])
            if not np.isnan(rho):
                ic_list.append(rho)

    if not ic_list:
        return 0.0, 0.0

    mean_ic = float(np.mean(ic_list))
    pos_frac = float(np.mean([1.0 if x > 0 else 0.0 for x in ic_list]))
    return mean_ic, pos_frac


def evaluate_micro_001_gates(
    oos_res: FactorSimulationResult,
    adverse_oos_res: FactorSimulationResult,
    prereg: FactorPreRegistration,
) -> dict[str, Any]:
    """Evaluates the 7 frozen pre-registration decision gates for EQ-Micro-001."""
    crit = prereg.pass_criteria

    net_sharpe = float(oos_res.annualized_net_sharpe)
    pos_frac = float(oos_res.ic_positive_fraction)
    mean_ic = float(oos_res.mean_rank_ic)
    monotonic = bool(oos_res.quantile_returns.get("monotonic", False))
    max_dd = float(oos_res.max_drawdown)
    friction_ratio = float(oos_res.costs.get("friction_drag_ratio", 1.0))
    adv_net_ret = float(adverse_oos_res.annualized_net_return)

    gate_1 = bool(net_sharpe >= crit["min_oos_net_sharpe"])
    gate_2 = bool(pos_frac >= crit["min_ic_positive_frac"])
    gate_3 = bool(mean_ic >= crit["min_mean_rank_ic"])
    gate_4 = bool(monotonic)
    gate_5 = bool(max_dd <= crit["max_drawdown"])
    gate_6 = bool(friction_ratio <= crit["max_friction_drag_ratio"])
    gate_7 = bool(adv_net_ret > crit["min_adverse_net_return"])

    gates = {
        "gate_1_oos_net_sharpe": gate_1,
        "gate_2_ic_positive_fraction": gate_2,
        "gate_3_mean_rank_ic": gate_3,
        "gate_4_quantile_monotonicity": gate_4,
        "gate_5_max_drawdown_limit": gate_5,
        "gate_6_friction_drag_ratio": gate_6,
        "gate_7_stressed_adverse_net_return": gate_7,
    }

    all_passed = all(gates.values())
    verdict = "candidate" if all_passed else "negative_result"

    out: dict[str, Any] = {
        "verdict": verdict,
        "gates": gates,
        "metrics": {
            "net_sharpe": net_sharpe,
            "annualized_net_return_pct": oos_res.annualized_net_return * 100.0,
            "max_drawdown_pct": max_dd * 100.0,
            "friction_drag_ratio": friction_ratio,
            "mean_rank_ic": mean_ic,
            "ic_positive_fraction": pos_frac,
            "adverse_net_return_pct": adv_net_ret * 100.0,
        },
    }

    if not all_passed:
        failed_gates = [k for k, v in gates.items() if not v]
        if not gate_2 or not gate_3 or not gate_4:
            out["failure_mode"] = "mechanism_failure"
            out["failure_mode_basis"] = (
                f"ETF constituent lead-lag signal exhibited structural mechanism breakdown: "
                f"Mean Rank IC ({mean_ic:.3f}) and IC positive fraction ({pos_frac:.1%}) "
                f"failed predictive thresholds, or quantile monotonicity was violated. Failed gates: {failed_gates}."
            )
            out["failure_mode_confidence"] = "high"
        else:
            out["failure_mode"] = "execution_constrained"
            out["failure_mode_basis"] = (
                f"Gross lead-lag alpha existed, but execution frictions (commissions, $1.00 min order fee, spread, impact) "
                f"consumed edge or breached Sharpe/drawdown thresholds. Friction ratio: {friction_ratio:.1%}. Failed gates: {failed_gates}."
            )
            out["failure_mode_confidence"] = "high"

    return out


def run_micro_screen_001(
    univ: EquitiesIntradayUniverseData,
    prereg: FactorPreRegistration | dict[str, Any],
    *,
    allow_oos_for_parameters: bool = False,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Runs the full EQ-Micro-001 research factor screen pipeline."""
    if isinstance(prereg, dict):
        prereg_obj = FactorPreRegistration.from_dict(prereg)
    else:
        prereg_obj = prereg

    missing = prereg_obj.missing_fields()
    if missing:
        raise EquitiesIntradayDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise EquitiesIntradayDataError("OOS partition cannot be used for parameter selection")
    if prereg_obj.hypothesis_id != "EQ-Micro-001":
        raise EquitiesIntradayDataError(f"run_micro_screen_001 requires EQ-Micro-001, got {prereg_obj.hypothesis_id}")

    is_univ = univ.slice_partition("IS")
    oos_univ = univ.slice_partition("OOS")

    # Signals
    is_signals = calculate_etf_intraday_lead_lag_signals(is_univ, prereg_obj.parameters)
    oos_signals = calculate_etf_intraday_lead_lag_signals(oos_univ, prereg_obj.parameters)

    # Cost schedules
    cost_baseline = FactorCostModel.baseline_ibkr_pro_fixed()
    cost_adverse = FactorCostModel.stressed_adverse()

    # Portfolio simulations
    is_res = simulate_intraday_lead_lag_portfolio(is_univ, is_signals, cost_baseline, prereg_obj.parameters, partition="IS")
    oos_res = simulate_intraday_lead_lag_portfolio(oos_univ, oos_signals, cost_baseline, prereg_obj.parameters, partition="OOS")
    adverse_oos_res = simulate_intraday_lead_lag_portfolio(oos_univ, oos_signals, cost_adverse, prereg_obj.parameters, partition="OOS_ADVERSE")

    # Gates
    gates_eval = evaluate_micro_001_gates(oos_res, adverse_oos_res, prereg_obj)

    bundle = {
        "hypothesis_id": "EQ-Micro-001",
        "manifest_digest": univ.manifest.digest(),
        "is": is_res.to_dict(),
        "oos": oos_res.to_dict(),
        "adverse_oos": adverse_oos_res.to_dict(),
        "gates": gates_eval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    out_file = output_path or (RESULTS_DIR / "EQ-Micro-001-evidence-bundle.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle
