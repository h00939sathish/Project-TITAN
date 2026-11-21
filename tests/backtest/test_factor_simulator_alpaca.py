"""Verifies factor portfolio simulation under Alpaca $0 retail cost schedule."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.backtest.alpaca_equity_costs import AlpacaEquityCostModel
from titan.backtest.factor_simulator import (
    FactorCostModel,
    simulate_factor_portfolio,
)
from titan.data.equities_universe import (
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.pead_factor import (
    calculate_pead_factor,
    calculate_quality_lowbeta_factor,
    composite_alpha_scores,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_equities_etf_v1.json"


def _universe() -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(42)
    series_map = {}
    for i, sym in enumerate(manifest.universe):
        drift = 0.0003 * (i + 1)
        rets = np.random.normal(drift, 0.012, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_alpaca_vs_ibkr_friction_comparison():
    univ, _ = _universe()
    pead = calculate_pead_factor(univ.prices, event_freq_days=21, vol_window=40)
    qual = calculate_quality_lowbeta_factor(univ.prices, vol_window=40, quality_lookback=60, skip=5)
    composite = composite_alpha_scores(pead, qual)

    # 1. Run simulation under standard IBKR Pro fixed schedule
    ibkr_cost = FactorCostModel.standard_us_equity()
    ibkr_res = simulate_factor_portfolio(
        univ,
        composite,
        hypothesis_id="PEAD_QUAL_IBKR",
        partition="OOS",
        top_k=2,
        bottom_k=2,
        rebalance_freq_days=21,
        cost_model=ibkr_cost,
    )

    # 2. Run simulation under Alpaca retail schedule ($0 comm, $0 ETB borrow)
    alpaca_model = AlpacaEquityCostModel.standard_retail()
    alpaca_sched = alpaca_model.to_venue_cost_schedule()
    alpaca_res = simulate_factor_portfolio(
        univ,
        composite,
        hypothesis_id="PEAD_QUAL_ALPACA",
        partition="OOS",
        top_k=2,
        bottom_k=2,
        rebalance_freq_days=21,
        cost_model=alpaca_sched,
    )

    # In Alpaca retail: commissions and short borrow MUST be 0.0
    assert alpaca_res.costs["total_commissions"] == 0.0
    assert alpaca_res.costs["total_borrow_cost"] == 0.0

    # In IBKR Pro: commissions and short borrow are strictly positive
    assert ibkr_res.costs["total_commissions"] > 0.0
    assert ibkr_res.costs["total_borrow_cost"] > 0.0

    # Total friction on Alpaca is substantially lower than IBKR Pro
    assert alpaca_res.costs["total_friction"] < ibkr_res.costs["total_friction"]

    # Consequently, net return and net Sharpe on Alpaca are strictly higher than IBKR
    assert alpaca_res.annualized_net_return > ibkr_res.annualized_net_return
    assert alpaca_res.annualized_net_sharpe > ibkr_res.annualized_net_sharpe
