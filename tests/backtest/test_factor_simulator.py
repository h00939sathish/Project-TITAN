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


def test_venue_cost_schedule_provenance_and_presets():
    from titan.backtest.factor_simulator import VenueCostSchedule

    alpaca = VenueCostSchedule.baseline_alpaca_us_equity()
    assert alpaca.name == "baseline_alpaca_us_equity"
    assert alpaca.layer == "layer1_discovery"
    assert alpaca.commission_per_share_usd == 0.0
    assert alpaca.assumption_status == "research_assumption"
    assert len(alpaca.digest()) == 64
    assert "https://alpaca.markets/disclosures" in alpaca.source_url

    ibkr_tiered = VenueCostSchedule.baseline_ibkr_pro_tiered()
    assert ibkr_tiered.name == "baseline_ibkr_pro_tiered"
    assert ibkr_tiered.commission_per_share_usd == 0.0035
    assert ibkr_tiered.min_commission_usd == 0.35
    assert ibkr_tiered.assumption_status == "research_assumption"
    assert len(ibkr_tiered.digest()) == 64

    ibkr_fixed = VenueCostSchedule.baseline_ibkr_pro_fixed()
    assert ibkr_fixed.name == "baseline_ibkr_pro_fixed"
    assert ibkr_fixed.commission_per_share_usd == 0.0050

    # Ensure to_dict retains provenance and digest
    d = ibkr_tiered.to_dict()
    assert d["layer"] == "layer1_discovery"
    assert d["effective_date"] == "2026-08-19"
    assert "digest" in d


def test_multi_venue_simulation_comparison():
    from titan.backtest.factor_simulator import VenueCostSchedule

    univ, _ = _universe()
    mom = factor_momentum_12_1m(univ.prices, lookback=252, skip=21)

    alpaca_model = VenueCostSchedule.baseline_alpaca_us_equity()
    ibkr_model = VenueCostSchedule.baseline_ibkr_pro_tiered()

    res_alpaca = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-004", cost_model=alpaca_model
    )
    res_ibkr = simulate_factor_portfolio(
        univ, mom, hypothesis_id="EQ-004", cost_model=ibkr_model
    )

    assert res_alpaca.costs["total_commissions"] == 0.0
    assert res_ibkr.costs["total_commissions"] > 0.0
    assert res_alpaca.cost_schedule is not None
    assert res_alpaca.cost_schedule.name == "baseline_alpaca_us_equity"

    # Verify result dictionary contains full provenance
    dict_out = res_alpaca.to_dict()
    assert "cost_schedule" in dict_out
    assert dict_out["cost_schedule"]["assumption_status"] == "research_assumption"


def test_digest_covers_all_material_fields():
    """Verify modifying any economic or provenance parameter perturbs the digest."""
    from dataclasses import replace
    from titan.backtest.factor_simulator import VenueCostSchedule

    base = VenueCostSchedule.baseline_ibkr_pro_tiered()
    base_digest = base.digest()

    mutations = [
        replace(base, spread_bps=0.85),
        replace(base, slippage_bps=0.35),
        replace(base, annual_short_borrow_bps=55.0),
        replace(base, commission_per_share_usd=0.0040),
        replace(base, min_commission_usd=0.50),
        replace(base, regulatory_fees_bps=0.05),
        replace(base, layer="layer2_historical"),
        replace(base, assumption_status="verified_from_published_schedule"),
        replace(base, effective_date="2026-08-20"),
        replace(base, source_document="Updated Fee Schedule"),
        replace(base, source_url="https://example.com/fees"),
        replace(base, provenance="Updated provenance note"),
    ]

    for mutated in mutations:
        assert mutated.digest() != base_digest, f"Mutation failed to alter digest: {mutated}"



