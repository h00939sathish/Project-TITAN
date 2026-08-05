import pytest
from datetime import datetime, timezone
from titan.data.normalize import normalize_row, _parse_timestamp
from titan.data.quality import validate_and_quarantine

def test_parse_timestamp_utc_normalization():
    dt_date = _parse_timestamp("2026-01-01")
    assert dt_date.tzinfo == timezone.utc
    assert dt_date.year == 2026 and dt_date.month == 1 and dt_date.day == 1

    dt_iso = _parse_timestamp("2026-01-01T14:30:00Z")
    assert dt_iso.tzinfo == timezone.utc
    assert dt_iso.hour == 14 and dt_iso.minute == 30

    row = {
        "symbol": "SPY",
        "date": "2026-01-01T14:30:00Z",
        "open": "450.0",
        "high": "452.0",
        "low": "449.0",
        "close": "451.0",
        "volume": "1000",
    }
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["timestamp"] == "2026-01-01T14:30:00Z"


def test_intraday_gap_quarantine():
    rows = [
        {"symbol": "SPY", "date": "2026-01-01T09:30:00Z", "open": "450.0", "high": "451.0", "low": "449.0", "close": "450.5", "volume": "100"},
        {"symbol": "SPY", "date": "2026-01-01T09:45:00Z", "open": "450.5", "high": "451.5", "low": "450.0", "close": "451.0", "volume": "100"},
        # 3 hour gap within same day (exceeds 5 * 15m = 75m threshold)
        {"symbol": "SPY", "date": "2026-01-01T13:00:00Z", "open": "451.0", "high": "452.0", "low": "450.5", "close": "451.5", "volume": "100"},
    ]
    report, good = validate_and_quarantine(
        rows,
        normalize_row,
        detect_intraday_gaps=True,
        expected_bar_interval_minutes=15,
    )
    assert report.passed == 2
    assert report.quarantine_count == 1
    assert "Intraday gap" in report.quarantined[0]["reason"]
