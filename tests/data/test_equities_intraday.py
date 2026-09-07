"""Tests for Equities and ETF 5-Minute Intraday Data Loader."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.data.equities_intraday import (
    EquitiesIntradayDataError,
    EquitiesIntradayManifest,
    build_intraday_universe,
)

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "research" / "equities" / "manifests" / "us_sp50_liquid_intraday_v1.json"


class TestEquitiesIntradayManifest:
    def test_load_manifest_succeeds(self):
        manifest = EquitiesIntradayManifest.load(MANIFEST_PATH)
        assert manifest.dataset_name == "us_sp50_liquid_intraday_v1"
        assert manifest.bar_interval == "5m"
        assert len(manifest.etf_anchors) == 4
        assert len(manifest.universe) == 50
        assert manifest.fee_schedule["min_commission_usd"] == 1.0
        assert len(manifest.digest()) == 64


class TestBuildIntradayUniverse:
    def test_alignment_produces_etf_and_stock_slices(self):
        manifest = EquitiesIntradayManifest.load(MANIFEST_PATH)
        dates = pd.date_range("2023-01-03 09:30:00", "2023-01-03 16:00:00", freq="5min")
        all_syms = manifest.etf_anchors + manifest.universe
        series_map = {}
        for s in all_syms:
            series_map[s] = pd.Series(100.0 + np.random.rand(len(dates)), index=dates)
        univ = build_intraday_universe(series_map, manifest)
        assert univ.prices.shape == (len(dates), len(all_syms))
        assert univ.etf_prices.shape == (len(dates), 4)
        assert univ.stock_prices.shape == (len(dates), 50)

    def test_missing_symbol_raises_data_error(self):
        manifest = EquitiesIntradayManifest.load(MANIFEST_PATH)
        with pytest.raises(EquitiesIntradayDataError):
            build_intraday_universe({"SPY": pd.Series([3])}, manifest)
