"""Tests for the data pipeline."""

from titan.data.ingest import checksum, read_csv
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "market"


class TestIngest:
    def test_checksum(self):
        path = FIXTURES / "sample_ohlcv.csv"
        cs = checksum(path)
        assert len(cs) == 64

    def test_read_csv(self):
        rows = read_csv(FIXTURES / "sample_ohlcv.csv")
        assert len(rows) == 6

    def test_read_csv_not_found(self):
        assert read_csv("nonexistent.csv") == []


class TestNormalize:
    def test_valid_row(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, dict)
        assert result["instrument_id"] == "AAPL"
        assert result["close"] == 151.0

    def test_unknown_symbol(self):
        row = {"symbol": "UNKNOWN", "date": "2026-01-02", "open": "100", "high": "100", "low": "100", "close": "100", "volume": "100"}
        assert isinstance(normalize_row(row), str)

    def test_invalid_date(self):
        row = {"symbol": "AAPL", "date": "not-a-date", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000000"}
        assert isinstance(normalize_row(row), str)

    def test_crossed_quote(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "155", "close": "151", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, str) and "low" in result

    def test_close_out_of_range(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "160", "volume": "1000000"}
        result = normalize_row(row)
        assert isinstance(result, str) and "Close" in result

    def test_negative_volume(self):
        row = {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "-100"}
        assert isinstance(normalize_row(row), str)


class TestQuality:
    def test_all_valid(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "MSFT", "date": "2026-01-02", "open": "400", "high": "405", "low": "398", "close": "402", "volume": "2000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 2
        assert report.quarantine_count == 0
        assert len(good) == 2

    def test_quarantine_bad_rows(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "UNKNOWN", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "AAPL", "date": "bad-date", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 1
        assert report.quarantine_count == 2

    def test_duplicate_quarantine(self):
        from titan.data.normalize import normalize_row
        rows = [
            {"symbol": "AAPL", "date": "2026-01-02", "open": "150", "high": "152", "low": "149", "close": "151", "volume": "1000"},
            {"symbol": "AAPL", "date": "2026-01-02", "open": "151", "high": "153", "low": "150", "close": "152", "volume": "1000"},
        ]
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 1
        assert report.quarantine_count == 1


class TestPipeline:
    def test_end_to_end_pipeline(self):
        """Ingest → normalize → quarantine → verify good records."""
        from titan.data.normalize import normalize_row
        rows = read_csv(FIXTURES / "sample_ohlcv.csv")
        assert len(rows) == 6
        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.passed == 6
        assert report.quarantine_count == 0
        assert len(good) == 6
        for r in good:
            assert "instrument_id" in r
            assert "timestamp" in r
            assert "close" in r
