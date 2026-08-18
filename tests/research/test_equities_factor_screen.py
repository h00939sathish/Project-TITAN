"""Tests for US Equities Cross-Sectional Factor Screen and Architectural Boundaries."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.equities_factor_screen import (
    FactorPreRegistration,
    load_factor_preregistration,
    run_factor_screen,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_equities_etf_v1.json"
HYP_DIR = ROOT / "research" / "equities" / "hypotheses"
SCREEN_PY = ROOT / "src" / "titan" / "research" / "equities_factor_screen.py"
FACTORS_PY = ROOT / "src" / "titan" / "research" / "factors.py"
SIM_PY = ROOT / "src" / "titan" / "backtest" / "factor_simulator.py"
UNIV_PY = ROOT / "src" / "titan" / "data" / "equities_universe.py"


def _universe() -> tuple:
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    np.random.seed(42)
    series_map = {}
    for i, sym in enumerate(manifest.universe):
        drift = 0.0001 * (i + 1)
        rets = np.random.normal(drift, 0.01, size=len(dates))
        prices = 100.0 * np.exp(np.cumsum(rets))
        series_map[sym] = pd.Series(prices, index=dates)

    univ = build_equities_universe(series_map, manifest)
    return univ, manifest


def test_missing_preregistration_fields_rejected():
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
        run_factor_screen(univ, prereg)


def test_oos_cannot_choose_parameters():
    prereg = load_factor_preregistration(HYP_DIR / "EQ-001-prereg.json")
    univ, _ = _universe()
    with pytest.raises(EquitiesDataError, match="OOS partition cannot be used"):
        run_factor_screen(univ, prereg, allow_oos_for_parameters=True)


def test_run_eq_001_momentum_screen():
    univ, _ = _universe()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-001-prereg.json")
    bundle = run_factor_screen(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-001"
    assert "is" in bundle
    assert "oos" in bundle
    assert "adverse_oos" in bundle
    assert bundle["gates"]["verdict"] in ("candidate", "negative_result")
    assert (ROOT / "research" / "equities" / "results" / "EQ-001-evidence-bundle.json").exists()


def test_run_eq_002_reversal_screen():
    univ, _ = _universe()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-002-prereg.json")
    bundle = run_factor_screen(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-002"
    assert (ROOT / "research" / "equities" / "results" / "EQ-002-evidence-bundle.json").exists()


def test_run_eq_003_lowvol_screen():
    univ, _ = _universe()
    prereg = load_factor_preregistration(HYP_DIR / "EQ-003-prereg.json")
    bundle = run_factor_screen(univ, prereg, replicated=False)

    assert bundle["hypothesis_id"] == "EQ-003"
    assert (ROOT / "research" / "equities" / "results" / "EQ-003-evidence-bundle.json").exists()


def test_factor_research_cannot_import_execution_engine():
    banned_imports = (
        "from titan.execution",
        "import titan.execution",
        "from titan.runtime",
    )
    for p in (SCREEN_PY, FACTORS_PY, SIM_PY, UNIV_PY):
        text = p.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"{token} found in {p}"
        assert "import TradeIntent" not in text
        assert "import PaperTradingEngine" not in text
        assert "import BrokerAdapter" not in text
