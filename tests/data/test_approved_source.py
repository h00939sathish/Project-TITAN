"""Tests for approved data source loading."""

from pathlib import Path

import pytest

from titan.data.approved import load_approved, ApprovedDataSource, DataSourceError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "market"


class TestLoadApproved:
    def test_load_valid_csv(self):
        source = load_approved(
            str(FIXTURES / "sample_ohlcv.csv"),
            min_bar_count=1,
            max_stale_trading_days=1000,
        )
        assert isinstance(source, ApprovedDataSource)
        assert source.instrument_id == "AAPL"
        assert source.bar_count() >= 1
        assert source.manifest.record_count == source.bar_count()

    def test_rejects_missing_file(self):
        with pytest.raises(DataSourceError, match="not found"):
            load_approved("/nonexistent/path.csv")

    def test_rejects_stale_data(self):
        with pytest.raises(DataSourceError, match="stale"):
            load_approved(
                str(FIXTURES / "sample_ohlcv.csv"),
                max_stale_trading_days=0,
            )

    def test_instrument_id_from_bars(self):
        source = load_approved(
            str(FIXTURES / "spy_2020_2024.csv"),
            min_bar_count=1,
            max_stale_trading_days=10000,
        )
        assert source.instrument_id == "SPY"
        assert source.bar_count() > 200

    def test_manifest_properties(self):
        source = load_approved(
            str(FIXTURES / "tlt_2020_2024.csv"),
            min_bar_count=1,
            max_stale_trading_days=10000,
        )
        assert source.manifest.source_checksum
        assert source.manifest.date_from
        assert source.manifest.date_to
        assert source.manifest.record_count == source.bar_count()

    def test_latest_bar_date(self):
        source = load_approved(
            str(FIXTURES / "sample_ohlcv.csv"),
            min_bar_count=1,
            max_stale_trading_days=10000,
        )
        assert source.latest_bar_date() is not None

    def test_empty_file_rejected(self):
        empty_file = FIXTURES / "sample_ohlcv.csv"
        with pytest.raises(DataSourceError, match="Insufficient valid bars"):
            load_approved(
                str(empty_file),
                min_bar_count=9999,
                max_stale_trading_days=10000,
            )
