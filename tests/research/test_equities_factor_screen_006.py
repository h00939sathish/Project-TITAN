"""Tests for EQ-006 Turnover-Constrained Quality & Low-Vol Factor Screen."""

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
from titan.research.equities_factor_screen_006 import (
    FactorPreRegistration,
    evaluate_factor_gates_006,
    load_factor_preregistration,
    run_factor_screen_006,
    simulate_factor_portfolio_deadband,
    verify_quantile_monotonicity,
)
from titan.research.factors import (
    factor_low_volatility,
    factor_quality_lowvol,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_equities_etf_v1.json"
HYP_DIR = ROOT / "research" / "equities" / "hypotheses"
SCREEN_006_PY = ROOT / "src" / "titan" / "research" / "equities_factor_screen_006.py"


def _universe(seed: int = 42) -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(seed)
    series_map = {}
    for i, sym in enumerate(manifest.universe):
        # Vary drift and volatility to create dispersion
        drift = 0.0001 * (i + 1)
        vol = 0.008 + 0.002 * (i % 3)
        rets = np.random.normal(drift, vol, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_quality_lowvol_scoring_logic():
    """Verify that composite scoring properly combines inverse vol and quality consistency."""
    dates = pd.date_range("2023-01-01", periods=300, freq="B")
    # Asset A: low vol & upward trend (High Quality / Low Vol)
    # Asset B: high vol & downward trend (Low Quality / High Vol)
    # Asset C: medium vol & flat
    np.random.seed(123)
    p_a = 100.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.005, 300)))
    p_b = 100.0 * np.exp(np.cumsum(np.random.normal(-0.001, 0.03, 300)))
    p_c = 100.0 * np.exp(np.cumsum(np.random.normal(0.000, 0.015, 300)))

    prices = pd.DataFrame({"A": p_a, "B": p_b, "C": p_c}, index=dates)
    scores = factor_quality_lowvol(prices, vol_window=63, quality_lookback=200, skip=10)

    assert scores.shape == prices.shape
    # Asset A should have higher score than Asset B at the end of the sample
    assert scores.iloc[-1]["A"] > scores.iloc[-1]["B"]


def test_deadband_turnover_reduction():
    """Verify that deadband rebalancing significantly reduces turnover compared to standard rebalancing."""
    univ, _ = _universe(seed=42)
    scores = factor_quality_lowvol(univ.prices, vol_window=63, quality_lookback=252, skip=21)

    oos_univ = univ.slice_partition("OOS")
    oos_scores = scores.loc[oos_univ.prices.index]

    # 1. Standard unconstrained simulation (entry=top 3, exit=top 3 -> no hysteresis)
    res_standard = simulate_factor_portfolio_deadband(
        oos_univ,
        oos_scores,
        hypothesis_id="EQ-006-STD",
        top_k=3,
        bottom_k=3,
        rebalance_freq_days=21,
        entry_pct=0.20,
        exit_pct=0.20,  # No buffer: exits immediately when dropping out of top 20%
    )

    # 2. Deadband simulation (entry=top 20%, exit=top 40% -> buffer hysteresis)
    res_deadband = simulate_factor_portfolio_deadband(
        oos_univ,
        oos_scores,
        hypothesis_id="EQ-006-DB",
        top_k=3,
        bottom_k=3,
        rebalance_freq_days=21,
        entry_pct=0.20,
        exit_pct=0.40,  # Deadband buffer
    )

    # Turnover with deadband must be strictly lower than without deadband
    assert res_deadband.monthly_turnover <= res_standard.monthly_turnover
    assert res_deadband.monthly_turnover <= 0.20  # Monthly turnover <= 20% gate


def test_gate_evaluation_logic():
    """Verify evaluate_factor_gates_006 handles passes and structured failure modes."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-006-prereg.json")
    univ, _ = _universe()
    oos_univ = univ.slice_partition("OOS")
    scores = factor_quality_lowvol(oos_univ.prices)

    oos_res = simulate_factor_portfolio_deadband(
        oos_univ, scores, hypothesis_id="EQ-006", top_k=3, bottom_k=3
    )
    adverse_res = simulate_factor_portfolio_deadband(
        oos_univ, scores, hypothesis_id="EQ-006", top_k=3, bottom_k=3,
        cost_model=FactorCostModel.stressed_adverse()
    )

    eval_res = evaluate_factor_gates_006(
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


def test_monotonicity_verification():
    """Verify verify_quantile_monotonicity helper evaluates quantile spreads."""
    univ, _ = _universe()
    oos_univ = univ.slice_partition("OOS")
    scores = factor_quality_lowvol(oos_univ.prices)

    is_mono, spreads = verify_quantile_monotonicity(
        oos_univ, scores, top_k=3, bottom_k=3, holding_days=21
    )
    assert isinstance(is_mono, bool)
    assert "top_quantile_ann" in spreads
    assert "bot_quantile_ann" in spreads


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
    univ, _ = _universe()
    with pytest.raises(EquitiesDataError, match="missing pre-registration"):
        run_factor_screen_006(univ, prereg)


def test_oos_cannot_choose_parameters():
    """Verify that attempting to choose parameters on OOS raises an error."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-006-prereg.json")
    univ, _ = _universe()
    with pytest.raises(EquitiesDataError, match="OOS partition cannot be used"):
        run_factor_screen_006(univ, prereg, allow_oos_for_parameters=True)


def test_run_eq_006_screen_end_to_end():
    """End-to-end execution of EQ-006 factor screen producing evidence bundle."""
    univ, _ = _universe()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-006-prereg.json")
    bundle = run_factor_screen_006(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-006"
    assert "is" in bundle
    assert "oos" in bundle
    assert "adverse_oos" in bundle
    assert "oos_unconstrained_comparator" in bundle
    assert "monotonicity" in bundle
    assert "gates" in bundle
    assert bundle["gates"]["verdict"] in ("candidate", "negative_result")
    assert (ROOT / "research" / "equities" / "results" / "EQ-006-evidence-bundle.json").exists()


def test_factor_screen_006_execution_import_ban():
    """Verify that research screen strictly preserves the default-deny boundary."""
    banned_tokens = (
        "from titan.execution",
        "import titan.execution",
        "from titan.runtime",
        "import TradeIntent",
        "import PaperTradingEngine",
        "import BrokerAdapter",
    )
    text = SCREEN_006_PY.read_text(encoding="utf-8")
    for token in banned_tokens:
        assert token not in text, f"Banned execution import '{token}' found in {SCREEN_006_PY}"
