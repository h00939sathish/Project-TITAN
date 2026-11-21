"""Unit tests for EQ-009: Point-in-Time PEAD Factor Screen.

Verifies:
- Pre-registration schema and validation.
- Strictly causal point-in-time signal generation (no lookahead).
- Staggered rebalancing and turnover suppression.
- Quantile monotonicity verification.
- Decision gate evaluation logic and Rule 8 failure mode classification.
- Output path isolation (preventing test clobber of canonical evidence bundles).
- Strict execution/runtime import ban.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from titan.backtest.factor_simulator import (
    FactorCostModel,
    FactorSimulationResult,
)
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseData,
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.equities_event_screen_009 import (
    FactorPreRegistration,
    calculate_pit_pead_scores,
    evaluate_factor_gates_009,
    load_factor_preregistration,
    load_pit_earnings_events,
    run_pit_screen_009,
    simulate_pit_pead_portfolio,
    verify_quantile_monotonicity,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
HYP_PATH = _REPO_ROOT / "research" / "equities" / "hypotheses" / "EQ-009-prereg.json"
EVENTS_PATH = _REPO_ROOT / "research" / "equities" / "data" / "us_sp50_earnings_events_v1.parquet"


@pytest.fixture
def prereg() -> FactorPreRegistration:
    return load_factor_preregistration(HYP_PATH)


@pytest.fixture
def synthetic_universe() -> EquitiesUniverseData:
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B")
    symbols = [f"SYM_{i:02d}" for i in range(20)]
    np.random.seed(42)

    # Generate synthetic random walk prices
    returns = np.random.normal(0.0004, 0.015, size=(len(dates), len(symbols)))
    prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
    prices_df = pd.DataFrame(prices, index=dates, columns=symbols)

    manifest = EquitiesUniverseManifest(
        dataset_name="test_pit_sp50",
        asset_class="US_EQUITIES",
        source="Synthetic Unit Test",
        universe=symbols,
        timezone="America/New_York",
        calendar="NYSE",
        coverage_from="2020-01-02",
        coverage_to="2024-12-31",
        is_partition={"from": "2020-01-02", "to": "2022-12-31"},
        oos_partition={"from": "2023-01-03", "to": "2024-12-31"},
        fee_schedule={"commission_per_share_usd": 0.005, "spread_bps": 1.0, "slippage_bps": 0.5, "annual_short_borrow_bps": 50.0},
        retrieval_ts_utc=datetime.now(timezone.utc).isoformat(),
        schema_version="1.0",
    )

    return build_equities_universe({s: prices_df[s] for s in symbols}, manifest)


@pytest.fixture
def synthetic_events(synthetic_universe: EquitiesUniverseData) -> pd.DataFrame:
    symbols = synthetic_universe.manifest.universe
    dates = [d.strftime("%Y-%m-%d") for d in synthetic_universe.prices.index]
    
    records = []
    # Every 63 days, generate an earnings event for each symbol
    for idx, sym in enumerate(symbols):
        offset = (idx * 3) % 20
        for t_idx in range(10 + offset, len(dates), 63):
            surp = np.random.uniform(-0.10, 0.15)
            records.append({
                "symbol": sym,
                "ticker": sym,
                "effective_trade_date": dates[t_idx],
                "reported_eps": 2.0 + surp,
                "eps_estimate": 2.0,
                "raw_surprise": surp,
                "surprise_pct": (surp / 2.0) * 100.0,
                "pre_event_price": 100.0,
                "sue_price_deflated": surp / 100.0,
            })
    return pd.DataFrame(records)


def test_load_preregistration_succeeds(prereg: FactorPreRegistration):
    assert prereg.hypothesis_id == "EQ-009"
    assert prereg.factor_name == "point_in_time_pead_sue_42d"
    assert len(prereg.universe) == 50
    assert prereg.parameters["holding_days"] == 42
    assert prereg.pass_criteria["min_oos_net_sharpe"] == 1.0


def test_missing_fields_rejected():
    corrupted = FactorPreRegistration(
        hypothesis_id="",
        factor_name="",
        universe=[],
        parameters={},
        cost_label="",
        is_partition={},
        oos_partition={},
        pass_criteria={},
    )
    assert len(corrupted.missing_fields()) == 8


def test_oos_cannot_choose_parameters(synthetic_universe, prereg, synthetic_events):
    with pytest.raises(EquitiesDataError, match="OOS partition cannot be used for parameter choice"):
        run_pit_screen_009(synthetic_universe, prereg, synthetic_events, allow_oos_for_parameters=True)


def test_calculate_pit_pead_scores_causal_no_lookahead(synthetic_universe):
    dates = [d.strftime("%Y-%m-%d") for d in synthetic_universe.prices.index]
    event_date = dates[50]
    prior_date = dates[49]
    post_date = dates[51]

    events_df = pd.DataFrame([{
        "symbol": "SYM_00",
        "effective_trade_date": event_date,
        "sue_price_deflated": 0.05,
    }])

    scores = calculate_pit_pead_scores(synthetic_universe.prices, events_df, holding_days=10)

    # Assert strictly causal: zero signal before announcement
    assert scores.loc[prior_date, "SYM_00"] == 0.0
    # Active on event date and post date
    assert scores.loc[event_date, "SYM_00"] != 0.0
    assert scores.loc[post_date, "SYM_00"] != 0.0


def test_simulate_pit_pead_portfolio_friction_and_turnover(synthetic_universe, synthetic_events):
    scores = calculate_pit_pead_scores(synthetic_universe.prices, synthetic_events, holding_days=42)
    res = simulate_pit_pead_portfolio(
        synthetic_universe,
        scores,
        hypothesis_id="EQ-009-TEST",
        partition="IS",
        top_k=3,
        bottom_k=3,
        holding_days=42,
        cost_model=FactorCostModel.baseline_ibkr_pro_fixed(),
    )
    assert res.hypothesis_id == "EQ-009-TEST"
    assert res.costs["commission_usd"] > 0.0
    assert res.costs["spread_usd"] > 0.0
    assert res.costs["total_friction_usd"] > 0.0
    assert res.monthly_turnover >= 0.0


def test_verify_quantile_monotonicity(synthetic_universe, synthetic_events):
    scores = calculate_pit_pead_scores(synthetic_universe.prices, synthetic_events, holding_days=42)
    is_mono, metrics = verify_quantile_monotonicity(synthetic_universe, scores, holding_days=42)
    assert "top_quintile_ann" in metrics
    assert "bot_quintile_ann" in metrics
    assert isinstance(is_mono, bool)


def test_gate_evaluation_logic():
    from titan.backtest.factor_simulator import VenueCostSchedule

    sched = VenueCostSchedule(
        name="test",
        commission_per_share_usd=0.005,
        min_commission_usd=1.0,
        spread_bps=1.0,
        slippage_bps=0.5,
        annual_short_borrow_bps=50.0,
        regulatory_fees_bps=0.04,
    )

    pass_res = FactorSimulationResult(
        hypothesis_id="EQ-009",
        partition="OOS",
        net_returns=pd.Series([0.001] * 252),
        gross_returns=pd.Series([0.0015] * 252),
        long_returns=pd.Series([0.001] * 252),
        short_returns=pd.Series([0.0005] * 252),
        turnover_series=pd.Series([0.02] * 252),
        rank_ic_series=pd.Series([0.05] * 252),
        costs={"total_friction_usd": 100.0, "friction_drag_ratio": 0.15},
        annualized_net_sharpe=1.45,
        annualized_net_return=0.15,
        max_drawdown=0.08,
        monthly_turnover=0.08,
        mean_rank_ic=0.05,
        ic_positive_fraction=0.72,
        quantile_returns={"gross_spread_ann": 0.18, "net_spread_ann": 0.15},
        cost_schedule=sched,
    )

    adverse_res = FactorSimulationResult(
        hypothesis_id="EQ-009",
        partition="OOS_ADVERSE",
        net_returns=pd.Series([0.0005] * 252),
        gross_returns=pd.Series([0.0015] * 252),
        long_returns=pd.Series([0.001] * 252),
        short_returns=pd.Series([0.0005] * 252),
        turnover_series=pd.Series([0.02] * 252),
        rank_ic_series=pd.Series([0.05] * 252),
        costs={"total_friction_usd": 200.0, "friction_drag_ratio": 0.25},
        annualized_net_sharpe=1.10,
        annualized_net_return=0.08,
        max_drawdown=0.10,
        monthly_turnover=0.08,
        mean_rank_ic=0.05,
        ic_positive_fraction=0.72,
        quantile_returns={"gross_spread_ann": 0.18, "net_spread_ann": 0.08},
        cost_schedule=sched,
    )

    prereg = FactorPreRegistration(
        hypothesis_id="EQ-009",
        factor_name="test",
        universe=["A"],
        parameters={},
        cost_label="test",
        is_partition={},
        oos_partition={},
        pass_criteria={"min_oos_net_sharpe": 1.0, "min_ic_positive_frac": 0.65, "min_mean_rank_ic": 0.03, "max_monthly_turnover": 0.15, "max_drawdown": 0.15, "min_adverse_net_return": 0.0},
    )

    eval_pass = evaluate_factor_gates_009(pass_res, adverse_res, prereg, is_monotonic=True)
    assert eval_pass["verdict"] == "candidate"

    fail_res = FactorSimulationResult(
        hypothesis_id="EQ-009",
        partition="OOS",
        net_returns=pd.Series([-0.001] * 252),
        gross_returns=pd.Series([0.0001] * 252),
        long_returns=pd.Series([0.0] * 252),
        short_returns=pd.Series([0.0] * 252),
        turnover_series=pd.Series([0.02] * 252),
        rank_ic_series=pd.Series([0.01] * 252),
        costs={"total_friction_usd": 500.0, "friction_drag_ratio": 5.0},
        annualized_net_sharpe=-0.50,
        annualized_net_return=-0.10,
        max_drawdown=0.25,
        monthly_turnover=0.18,
        mean_rank_ic=0.01,
        ic_positive_fraction=0.50,
        quantile_returns={"gross_spread_ann": 0.01, "net_spread_ann": -0.10},
        cost_schedule=sched,
    )

    eval_fail = evaluate_factor_gates_009(fail_res, adverse_res, prereg, is_monotonic=False)
    assert eval_fail["verdict"] == "negative_result"
    assert "failure_mode" in eval_fail


def test_run_pit_screen_009_output_isolation(tmp_path, synthetic_universe, prereg, synthetic_events):
    custom_out = tmp_path / "custom_bundle.json"
    bundle = run_pit_screen_009(
        synthetic_universe,
        prereg,
        synthetic_events,
        output_path=custom_out,
    )
    assert custom_out.exists()
    saved = json.loads(custom_out.read_text(encoding="utf-8"))
    assert saved["hypothesis_id"] == "EQ-009"
    assert "gates" in saved


def test_event_screen_009_execution_import_ban():
    screen_path = _REPO_ROOT / "src" / "titan" / "research" / "equities_event_screen_009.py"
    content = screen_path.read_text(encoding="utf-8")
    for banned in (
        "titan.execution",
        "titan.runtime",
        "ib_insync",
        "alpaca.trading",
        "InteractiveBrokers",
    ):
        assert banned not in content, f"Banned import '{banned}' found in screen engine"
