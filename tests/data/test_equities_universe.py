"""Tests for Equities Universe Loader and Manifest."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pytest

from titan.data.equities_universe import (
    EquitiesDataError,
    EquitiesUniverseManifest,
    build_equities_universe,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "equities" / "manifests" / "us_equities_etf_v1.json"


def _manifest() -> EquitiesUniverseManifest:
    return EquitiesUniverseManifest.load(MANIFEST_PATH)


def test_manifest_loads_correctly():
    manifest = _manifest()
    assert manifest.dataset_name == "us_equities_etf_v1"
    assert "SPY" in manifest.universe
    assert "QQQ" in manifest.universe
    assert manifest.fee_schedule["commission_per_share_usd"] == 0.005
    assert len(manifest.digest()) == 64


def test_build_universe_validates_required_symbols():
    manifest = _manifest()
    # Missing some symbols from the universe
    dates = pd.date_range("2020-01-01", periods=100, freq="B").strftime("%Y-%m-%d")
    series_map = {
        "SPY": pd.Series(100.0, index=dates),
        "QQQ": pd.Series(200.0, index=dates),
    }
    with pytest.raises(EquitiesDataError, match="not found in provided series"):
        build_equities_universe(series_map, manifest)


def test_build_universe_aligns_and_slices_partitions():
    manifest = _manifest()
    dates = pd.date_range("2020-01-02", "2024-12-31", freq="B").strftime("%Y-%m-%d")
    series_map = {sym: pd.Series(100.0 + i * 5.0, index=dates) for i, sym in enumerate(manifest.universe)}
    
    univ = build_equities_universe(series_map, manifest)
    assert univ.prices.shape[1] == len(manifest.universe)
    assert univ.returns.shape[1] == len(manifest.universe)

    is_univ = univ.slice_partition("IS")
    assert is_univ.prices.index[0] >= "2020-01-02"
    assert is_univ.prices.index[-1] <= "2022-12-31"

    oos_univ = univ.slice_partition("OOS")
    assert oos_univ.prices.index[0] >= "2023-01-03"
    assert oos_univ.prices.index[-1] <= "2024-12-31"
