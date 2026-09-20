"""Tests for EQ-007 Post-Earnings Announcement Drift (PEAD) Screen."""

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
from titan.research.equities_event_screen_007 import (
    FactorPreRegistration,
    calculate_pead_surprise_scores,
    evaluate_factor_gates_007,
    load_factor_preregistration,
    run_event_screen_007,
    simulate_pead_drift_portfolio,
    verify_quantile_monotonicity,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_core_7_equities_v1.json"
HYP_DIR = ROOT / "research" / "equities" / "hypotheses"
SCREEN_007_PY = ROOT / "src" / "titan" / "research" / "equities_event_screen_007.py"


def _universe(seed: int = 42) -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(seed)
    series_map = {}
    for i, sym in enumerate(manifest.universe):
        # Vary drift and volatility to create realistic dispersion
        drift = 0.0002 * (i + 1)
        vol = 0.010 + 0.002 * (i % 3)
        rets = np.random.normal(drift, vol, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_pead_surprise_signal_extraction():
    """Verify that PEAD surprise scores extract event jumps and persist across 42-day holding window."""
    dates = pd.date_range("2023-01-01", periods=200, freq="B").strftime("%Y-%m-%d")
    np.random.seed(99)
    # Generate prices for 4 assets
    p_spy = 100.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.01, 200)))
    p_a = 100.0 * np.exp(np.cumsum(np.random.normal(0.0008, 0.015, 200)))
    p_b = 100.0 * np.exp(np.cumsum(np.random.normal(-0.0005, 0.015, 200)))
    p_c = 100.0 * np.exp(np.cumsum(np.random.normal(0.0000, 0.012, 200)))

    # Inject large positive earnings jump into asset A at event date t=63
    p_a[63:] *= 1.08  # +8% jump
    # Inject large negative earnings jump into asset B at event date t=63
    p_b[63:] *= 0.92  # -8% jump

    prices = pd.DataFrame({"SPY": p_spy, "A": p_a, "B": p_b, "C": p_c}, index=dates)
    scores = calculate_pead_surprise_scores(
        prices,
        benchmark_col="SPY",
        event_freq_days=63,
        vol_window=63,
        holding_days=42,
    )

    assert scores.shape == prices.shape
    # At event date t=63 and across the 42-day holding window (e.g. t=70), Asset A must have highest score
    assert scores.iloc[63]["A"] > scores.iloc[63]["B"]
    assert scores.iloc[70]["A"] > scores.iloc[70]["B"]
    assert scores.iloc[63 + 41]["A"] > scores.iloc[63 + 41]["B"]


def test_multi_week_drift_holding_and_turnover_budget():
    """Verify that 42-day holding horizon satisfies low-turnover budget (<= 20% on synthetic, <= 15% on real Core-7)."""
    univ, _ = _universe(seed=42)
    scores = calculate_pead_surprise_scores(
        univ.prices,
        event_freq_days=63,
        vol_window=63,
        holding_days=42,
    )

    oos_univ = univ.slice_partition("OOS")
    oos_scores = scores.loc[oos_univ.prices.index]

    res = simulate_pead_drift_portfolio(
        oos_univ,
        oos_scores,
        hypothesis_id="EQ-007",
        partition="OOS",
        top_k=2,
        bottom_k=2,
        holding_days=42,
        event_freq_days=63,
    )

    # Monthly turnover on synthetic random series
    assert res.monthly_turnover <= 0.20
    assert res.annualized_net_sharpe is not None
    assert "total_friction" in res.costs
    assert res.costs["total_borrow_cost"] >= 0.0

    # Verify on real Core-7 market fixture if present
    data_dir = ROOT / "tests" / "fixtures" / "market"
    if (data_dir / "real_spy_2019_2024.csv").exists():
        manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
        series_dict = {
            sym: pd.read_csv(data_dir / f"real_{sym.lower()}_2019_2024.csv", index_col="date", parse_dates=True)["adj_close"]
            for sym in manifest.universe
        }
        real_univ = build_equities_universe(series_dict, manifest)
        real_scores = calculate_pead_surprise_scores(real_univ.prices)
        real_oos = real_univ.slice_partition("OOS")
        real_res = simulate_pead_drift_portfolio(
            real_oos,
            real_scores.loc[real_oos.prices.index],
            hypothesis_id="EQ-007",
            partition="OOS",
            top_k=2,
            bottom_k=2,
        )
        assert real_res.monthly_turnover <= 0.15


def test_gate_evaluation_logic():
    """Verify evaluate_factor_gates_007 handles candidate and Rule 8 failure mode attribution."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-007-prereg.json")
    univ, _ = _universe()
    oos_univ = univ.slice_partition("OOS")
    scores = calculate_pead_surprise_scores(oos_univ.prices)

    oos_res = simulate_pead_drift_portfolio(
        oos_univ, scores, hypothesis_id="EQ-007", top_k=2, bottom_k=2
    )
    adverse_res = simulate_pead_drift_portfolio(
        oos_univ,
        scores,
        hypothesis_id="EQ-007",
        top_k=2,
        bottom_k=2,
        cost_model=FactorCostModel.stressed_adverse(),
    )

    eval_res = evaluate_factor_gates_007(
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
    """Verify verify_quantile_monotonicity computes quantile spreads."""
    univ, _ = _universe()
    oos_univ = univ.slice_partition("OOS")
    scores = calculate_pead_surprise_scores(oos_univ.prices)

    is_mono, spreads = verify_quantile_monotonicity(
        oos_univ, scores, top_k=2, bottom_k=2, holding_days=42
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
        run_event_screen_007(univ, prereg)


def test_oos_cannot_choose_parameters():
    """Verify that attempting to choose parameters on OOS raises an error."""
    prereg = load_factor_preregistration(HYP_DIR / "EQ-007-prereg.json")
    univ, _ = _universe()
    with pytest.raises(EquitiesDataError, match="OOS partition cannot be used"):
        run_event_screen_007(univ, prereg, allow_oos_for_parameters=True)


def test_run_eq_007_screen_end_to_end():
    """End-to-end execution of EQ-007 PEAD screen producing evidence bundle."""
    univ, _ = _universe()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-007-prereg.json")
    bundle = run_event_screen_007(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-007"
    assert "is" in bundle
    assert "oos" in bundle
    assert "adverse_oos" in bundle
    assert "monotonicity" in bundle
    assert "gates" in bundle
    assert bundle["gates"]["verdict"] in ("candidate", "negative_result")

    out_bundle_path = ROOT / "research" / "equities" / "results" / "EQ-007-evidence-bundle.json"
    assert out_bundle_path.exists()


def test_event_screen_007_execution_import_ban():
    """Verify that PEAD event screen strictly preserves the default-deny execution boundary."""
    banned_tokens = (
        "from titan.execution",
        "import titan.execution",
        "from titan.runtime",
        "import TradeIntent",
        "import PaperTradingEngine",
        "import BrokerAdapter",
    )
    text = SCREEN_007_PY.read_text(encoding="utf-8")
    for token in banned_tokens:
        assert token not in text, f"Banned execution import '{token}' found in {SCREEN_007_PY}"
