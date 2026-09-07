"""Tests for EQ-008 Broad Universe Staggered Post-Earnings Announcement Drift (PEAD) Screen."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.backtest.factor_simulator import FactorCostModel
from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.equities_event_screen_008 import (
    FactorPreRegistration,
    calculate_staggered_pead_scores,
    evaluate_factor_gates_008,
    load_factor_preregistration,
    run_event_screen_008,
    simulate_staggered_pead_portfolio,
    verify_quantile_monotonicity,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_sp50_liquid_v1.json"
HYP_DIR = ROOT / "research" / "equities" / "hypotheses"
SCREEN_008_PY = ROOT / "src" / "titan" / "research" / "equities_event_screen_008.py"


def _universe_sp50(seed: int = 42) -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(seed)
    n_assets = len(manifest.universe)
    series_map = {}

    for i, sym in enumerate(manifest.universe):
        # Vary drift and volatility across sectors
        drift = 0.0001 * (1 + (i % 5))
        vol = 0.012 + 0.001 * (i % 4)
        rets = np.random.normal(drift, vol, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_staggered_pead_surprise_signal_extraction():
    """Verify that staggered PEAD surprise scores extract event jumps and persist across 42-day holding window."""
    dates = pd.date_range("2023-01-01", periods=250, freq="B").strftime("%Y-%m-%d")
    np.random.seed(99)
    # Generate prices for 10 assets
    cols = [f"SYM_{i:02d}" for i in range(10)]
    price_dict = {}
    for sym in cols:
        price_dict[sym] = 100.0 * np.exp(np.cumsum(np.random.normal(0.0004, 0.015, 250)))

    prices = pd.DataFrame(price_dict, index=dates)

    # Offset for SYM_00: floor(0 * 63 / 10) = 0 -> event at 63 + 0 = 63
    # Offset for SYM_05: floor(5 * 63 / 10) = 31 -> event at 63 + 31 = 94
    # Inject large positive earnings jump into SYM_00 at t=63
    prices.iloc[63:, 0] *= 1.08  # +8% jump
    # Inject large negative earnings jump into SYM_01 at t=63 + 6 = 69
    prices.iloc[69:, 1] *= 0.92  # -8% jump

    scores = calculate_staggered_pead_scores(
        prices,
        event_freq_days=63,
        vol_window=63,
        holding_days=42,
    )

    assert scores.shape == prices.shape
    # SYM_00 event at t=63: score must be positive across holding window [63, 104]
    assert scores.iloc[63]["SYM_00"] > 0
    assert scores.iloc[75]["SYM_00"] > 0
    assert scores.iloc[104]["SYM_00"] > 0

    # SYM_01 event at t=69: score must be negative across holding window [69, 110]
    assert scores.iloc[69]["SYM_01"] < 0
    assert scores.iloc[80]["SYM_01"] < 0


def test_staggered_rebalancing_turnover_reduction():
    """Verify that staggered 42-day holding horizon suppresses monthly turnover (<= 12.0%, target <= 10.0%)."""
    univ, _ = _universe_sp50(seed=42)
    scores = calculate_staggered_pead_scores(
        univ.prices,
        event_freq_days=63,
        vol_window=63,
        holding_days=42,
    )

    oos_univ = univ.slice_partition("OOS")
    oos_scores = scores.loc[oos_univ.prices.index]

    res = simulate_staggered_pead_portfolio(
        oos_univ,
        oos_scores,
        hypothesis_id="EQ-008",
        partition="OOS",
        top_k=10,
        bottom_k=10,
        holding_days=42,
        event_freq_days=63,
    )

    # Monthly turnover must be strictly <= 12.0%/month
    assert res.monthly_turnover <= 0.12
    assert res.annualized_net_sharpe is not None
    assert "total_friction" in res.costs
    assert res.costs["total_borrow_cost"] >= 0.0
    assert res.costs["total_commissions"] > 0.0


def test_gate_evaluation_logic():
    """Verify evaluate_factor_gates_008 handles candidate and Rule 8 failure mode attribution."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-008-prereg.json")
    univ, _ = _universe_sp50()
    oos_univ = univ.slice_partition("OOS")
    scores = calculate_staggered_pead_scores(oos_univ.prices)

    oos_res = simulate_staggered_pead_portfolio(
        oos_univ, scores, hypothesis_id="EQ-008", top_k=10, bottom_k=10
    )
    adverse_res = simulate_staggered_pead_portfolio(
        oos_univ,
        scores,
        hypothesis_id="EQ-008",
        top_k=10,
        bottom_k=10,
        cost_model=FactorCostModel.stressed_adverse(),
    )

    eval_res = evaluate_factor_gates_008(
        oos_res, adverse_res, prereg, is_monotonic=True, replicated=True
    )
    assert "verdict" in eval_res
    assert "gates" in eval_res
    assert "metrics" in eval_res
    if eval_res["verdict"] == "negative_result":
        assert "failure_mode" in eval_res
        assert eval_res["failure_mode"] in (
            "mechanism_failure",
            "execution_constrained_rejection",
            "overfit_regime_fragile",
        )
        assert len(eval_res["failure_mode_basis"]) > 0
        assert eval_res["failure_mode_confidence"] == "high"


def test_monotonicity_verification():
    """Verify verify_quantile_monotonicity computes quintile spreads."""
    univ, _ = _universe_sp50()
    oos_univ = univ.slice_partition("OOS")
    scores = calculate_staggered_pead_scores(oos_univ.prices)

    is_mono, spreads = verify_quantile_monotonicity(
        oos_univ, scores, holding_days=42, num_quantiles=5
    )
    assert isinstance(is_mono, bool)
    assert "top_quantile_ann" in spreads
    assert "bot_quantile_ann" in spreads
    assert "quintile_returns" in spreads


def test_missing_preregistration_fields_rejected():
    """Verify incomplete pre-registrations are rejected."""
    prereg = FactorPreRegistration(
        hypothesis_id="",
        factor_name="",
        universe=[],
        parameters={},
        cost_label="",
        is_partition={},
        oos_partition={},
        pass_criteria={},
    )
    univ, _ = _universe_sp50()
    with pytest.raises(EquitiesDataError, match="missing pre-registration"):
        run_event_screen_008(univ, prereg)


def test_oos_cannot_choose_parameters():
    """Verify that attempting to choose parameters on OOS raises an error."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-008-prereg.json")
    univ, _ = _universe_sp50()
    with pytest.raises(EquitiesDataError, match="OOS partition cannot be used"):
        run_event_screen_008(univ, prereg, allow_oos_for_parameters=True)


def test_run_eq_008_screen_end_to_end():
    """End-to-end execution of EQ-008 Staggered PEAD screen producing evidence bundle."""
    univ, _ = _universe_sp50()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-008-prereg.json")
    bundle = run_event_screen_008(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-008"
    assert "is" in bundle
    assert "oos" in bundle
    assert "adverse_oos" in bundle
    assert "monotonicity" in bundle
    assert "gates" in bundle
    assert bundle["gates"]["verdict"] in ("candidate", "negative_result")

    out_bundle_path = ROOT / "research" / "equities" / "results" / "EQ-008-evidence-bundle.json"
    assert out_bundle_path.exists()


def test_event_screen_008_execution_import_ban():
    """Verify that PEAD event screen strictly preserves the default-deny execution boundary."""
    banned_tokens = (
        "from titan.execution",
        "import titan.execution",
        "from titan.runtime",
        "import TradeIntent",
        "import PaperTradingEngine",
        "import BrokerAdapter",
    )
    text = SCREEN_008_PY.read_text(encoding="utf-8")
    for token in banned_tokens:
        assert token not in text, f"Banned execution import '{token}' found in {SCREEN_008_PY}"
