"""Tests for data freshness/staleness checks."""

from datetime import date

from titan.data.manifest import DataManifest
from titan.data.freshness import check_freshness, coverage_days


def _make_manifest(date_to: str, date_from: str = "2026-01-02T00:00:00", record_count: int = 100) -> DataManifest:
    return DataManifest(
        source_path="test.csv",
        source_checksum="abc",
        instrument_id="SPY",
        date_from=date_from,
        date_to=date_to,
        record_count=record_count,
        applied_adjustments=[],
    )


class TestCheckFreshness:
    def test_fresh_data(self):
        manifest = _make_manifest("2026-07-13T00:00:00")
        result = check_freshness(manifest, reference_date=date(2026, 7, 14))
        assert result.fresh
        assert result.trading_days_stale == 0

    def test_stale_by_one_day(self):
        manifest = _make_manifest("2026-07-10T00:00:00")
        result = check_freshness(manifest, reference_date=date(2026, 7, 14))
        assert result.fresh
        assert result.trading_days_stale == 1

    def test_stale_beyond_tolerance(self):
        manifest = _make_manifest("2026-07-08T00:00:00")
        result = check_freshness(manifest, reference_date=date(2026, 7, 14), max_stale_trading_days=2)
        assert not result.fresh
        assert result.trading_days_stale is not None
        assert result.trading_days_stale >= 3

    def test_empty_manifest(self):
        manifest = _make_manifest("")
        result = check_freshness(manifest)
        assert not result.fresh
        assert result.reason == "Manifest has no date_to — no data"

    def test_over_weekend(self):
        """Data from Friday should be fresh on Monday."""
        manifest = _make_manifest("2026-07-10T00:00:00")
        result = check_freshness(manifest, reference_date=date(2026, 7, 13))
        assert result.fresh
        assert result.trading_days_stale == 0

    def test_holiday_week(self):
        """Jul 3 is observed Indep Day — Jul 2 (Thu) data should be fresh on Jul 6 (Mon)."""
        manifest = _make_manifest("2026-07-02T00:00:00")
        result = check_freshness(manifest, reference_date=date(2026, 7, 6))
        assert result.fresh

    def test_tolerance_tunable(self):
        manifest = _make_manifest("2026-07-08T00:00:00")
        loose = check_freshness(manifest, reference_date=date(2026, 7, 14), max_stale_trading_days=10)
        assert loose.fresh
        strict = check_freshness(manifest, reference_date=date(2026, 7, 14), max_stale_trading_days=1)
        assert not strict.fresh


class TestCoverageDays:
    def test_normal_coverage(self):
        manifest = _make_manifest("2026-07-13T00:00:00", date_from="2025-07-14T00:00:00")
        assert coverage_days(manifest) == 364

    def test_empty_manifest(self):
        manifest = _make_manifest("", date_from="")
        assert coverage_days(manifest) == 0

    def test_single_day(self):
        manifest = _make_manifest("2026-07-14T00:00:00", date_from="2026-07-14T00:00:00")
        assert coverage_days(manifest) == 0
