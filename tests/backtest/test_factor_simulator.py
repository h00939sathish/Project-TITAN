"""Tests for Market-Neutral Factor Simulator & Cost Attribution."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.backtest.factor_simulator import (
    FactorCostModel,
    simulate_factor_portfolio,
)
from titan.data.equities_universe import (
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.factors import factor_momentum_12_1m

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_equities_etf_v1.json"


def _universe() -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(42)
    # Generate random walk prices for universe
    series_map = {}
    for i, sym in enumerate(manifest.universe):
        drift = 0.0002 * (i + 1)
        rets = np.random.normal(drift, 0.01, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_factor_simulation_computes_attribution_and_neutrality():
    univ, _ = _universe()
    mom = factor_momentum_12_1m(univ.prices, lookback=252, skip=21)
    
    cost = FactorCostModel.standard_us_equity()
    res = simulate_factor_portfolio(
        univ,
        mom,
        hypothesis_id="EQ-001",
        partition="OOS",
        top_k=2,
        bottom_k=2,
        rebalance_freq_days=21,
        cost_model=cost,
    )
    
    assert res.hypothesis_id == "EQ-001"
    assert res.partition == "OOS"
    assert "total_borrow_cost" in res.costs
    assert "total_commissions" in res.costs
    assert "total_spread" in res.costs
    assert "total_slippage" in res.costs
    assert res.costs["total_borrow_cost"] > 0
    assert res.costs["total_slippage"] >= 0
    assert len(res.net_returns) == len(univ.prices)
    assert isinstance(res.annualized_net_sharpe, float)
    assert isinstance(res.mean_rank_ic, float)


def test_gross_exposure_configuration():
    univ, _ = _universe()
    mom = factor_momentum_12_1m(univ.prices, lookback=252, skip=21)

    # Test default gross exposure (1.0 = +50% / -50%)
    res_1x = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-001", top_k=2, bottom_k=2, gross_exposure=1.0
    )
    # Test 200% gross exposure (2.0 = +100% / -100%)
    res_2x = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-001", top_k=2, bottom_k=2, gross_exposure=2.0
    )

    # 2x gross exposure should produce approximately 2x gross returns and 2x borrow costs
    assert abs(res_2x.costs["total_borrow_cost"] - 2.0 * res_1x.costs["total_borrow_cost"]) < 1e-4
    assert abs(res_2x.costs["total_commissions"] - 2.0 * res_1x.costs["total_commissions"]) < 1e-4


def test_stressed_cost_model_increases_friction():
    univ, _ = _universe()
    mom = factor_momentum_12_1m(univ.prices, lookback=252, skip=21)

    std_res = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-001", cost_model=FactorCostModel.standard_us_equity()
    )
    stress_res = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-001", cost_model=FactorCostModel.stressed_adverse()
    )

    assert stress_res.costs["total_friction"] > std_res.costs["total_friction"]
    assert stress_res.costs["total_slippage"] > std_res.costs["total_slippage"]
    assert stress_res.annualized_net_return <= std_res.annualized_net_return

