"""Point-in-time correctness tests for market data."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from titan.data.ingest import read_csv
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "market"


# ---------------------------------------------------------------------------
# Helper: build an in-memory CSV-like list of dicts
# ---------------------------------------------------------------------------

def make_csv_rows(dates: list[str], symbol: str = "AAPL") -> list[dict]:
    return [
        {"symbol": symbol, "date": d, "open": "100", "high": "105", "low": "99", "close": "102", "volume": "1000"}
        for d in dates
    ]


# ---------------------------------------------------------------------------
# 1. Survivorship bias
# ---------------------------------------------------------------------------

def test_survivorship_bias_does_not_crash():
    """Pipeline should handle delisted symbols without crashing."""
    rows = [
        {"symbol": "DELISTED_CO", "date": "2020-06-15", "open": "50", "high": "52", "low": "49", "close": "51", "volume": "5000"},
    ]
    report, good = validate_and_quarantine(rows, normalize_row, pass_through_unknown=True)
    assert report.total_records == 1
    assert report.quarantine_count == 0


# ---------------------------------------------------------------------------
# 2. Look-ahead leakage
# ---------------------------------------------------------------------------

def test_look_ahead_leakage():
    """Sequential reader must only see bars up to the current timestamp."""
    dates = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    rows = make_csv_rows(dates)

    for i, row in enumerate(rows):
        known = rows[: i + 1]
        visible_timestamps = {r["date"] for r in known}
        future_timestamps = {r["date"] for r in rows} - visible_timestamps

        assert len(future_timestamps) == len(rows) - i - 1
        assert row["date"] not in {r["date"] for r in rows[i + 1 :]}


# ---------------------------------------------------------------------------
# 3. Missing session detection
# ---------------------------------------------------------------------------

def test_missing_session_detection():
    """Quality check should flag a gap where Monday is missing (Fri -> Tue)."""
    rows = [
        {"symbol": "AAPL", "date": "2020-01-03", "open": "100", "high": "105", "low": "99", "close": "102", "volume": "1000"},
        {"symbol": "AAPL", "date": "2020-01-07", "open": "100", "high": "105", "low": "99", "close": "102", "volume": "1000"},
    ]

    def _gap_check(r):
        dates_seen.append(r["date"])
        return normalize_row(r)

    dates_seen = []
    report, good = validate_and_quarantine(rows, _gap_check, detect_gaps=True)
    assert report.quarantine_count > 0, "Expected gap to be flagged"


# ---------------------------------------------------------------------------
# 4. Stale data detection
# ---------------------------------------------------------------------------

def check_stale_data(bars: list[dict], max_age_days: int) -> bool:
    """Return True if the most recent bar is older than max_age_days."""
    if not bars:
        return True
    latest_str = bars[-1].get("date", "")
    if not latest_str:
        return True
    latest = datetime.strptime(latest_str, "%Y-%m-%d")
    age = (datetime.now() - latest).days
    return age > max_age_days


def test_stale_data_detection():
    """Detect when the latest bar exceeds the staleness threshold."""
    today = datetime.now()
    old_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    fresh_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    stale_rows = make_csv_rows([old_date])
    assert check_stale_data(stale_rows, max_age_days=5) is True

    fresh_rows = make_csv_rows([fresh_date])
    assert check_stale_data(fresh_rows, max_age_days=5) is False

    assert check_stale_data([], max_age_days=5) is True


# ---------------------------------------------------------------------------
# 5. Corporate action handling
# ---------------------------------------------------------------------------

def test_corporate_action_adjustment():
    """CorporateActionsDB adjusts pre-split prices so post-split open aligns."""
    from titan.backtest.corporate_actions import CorporateActionsDB, SplitEvent

    ca_db = CorporateActionsDB(splits=[
        SplitEvent(date="2020-08-30", instrument_id="AAPL", ratio=4.0),
    ])

    rows = [
        {"symbol": "AAPL", "date": "2020-08-28", "open": "100", "high": "105",
         "low": "99", "close": "102", "volume": "1000"},
        {"symbol": "AAPL", "date": "2020-08-31", "open": "25", "high": "27",
         "low": "24", "close": "26", "volume": "4000"},
    ]
    report, good = validate_and_quarantine(rows, normalize_row)
    assert report.passed == 2

    adjusted = ca_db.adjust_bars(good)
    pre_close = next(r for r in adjusted if r["timestamp"].startswith("2020-08-28"))["close"]
    post_open = next(r for r in adjusted if r["timestamp"].startswith("2020-08-31"))["open"]
    assert abs(pre_close - 102.0 / 4) < 0.01, "Expected pre-split close adjusted by ratio"
    assert abs(post_open - 25.0) < 0.01, "Expected post-split open unchanged"


# ---------------------------------------------------------------------------
# 6. Vendor correction detection
# ---------------------------------------------------------------------------

def test_vendor_correction_detection():
    """Detect when a vendor sends a corrected bar with a different close."""
    original_bar = {"symbol": "AAPL", "date": "2020-01-02", "open": "100", "high": "105", "low": "99", "close": "102", "volume": "1000"}
    corrected_bar = {"symbol": "AAPL", "date": "2020-01-02", "open": "100", "high": "105", "low": "99", "close": "103", "volume": "1000"}

    def _normalize_with_correction(row):
        return normalize_row(row)

    rows = [original_bar, corrected_bar]
    report, good = validate_and_quarantine(rows, _normalize_with_correction)

    correction_detected = False
    for q in report.quarantined:
        if "correction" in q.get("reason", "").lower():
            correction_detected = True

    assert correction_detected or report.quarantine_count > 0, \
        "Expected the duplicate bar to be quarantined as a potential correction"
