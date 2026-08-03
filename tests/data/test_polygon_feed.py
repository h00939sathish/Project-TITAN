"""Tests for Polygon.io data feed -- skipped without API key."""

import os
import pytest

from titan.data.polygon_feed import (
    fetch_daily_bars,
    fetch_batch,
    POLYGON_TICKER_MAP,
)
from titan.data.approved import DataSourceError


def test_ticker_mapping_covers_all_symbols():
    from titan.data.forex_pairs import FOREX_SYMBOLS
    from titan.data.spot_metals import SPOT_METAL_SYMBOLS
    all_symbols = FOREX_SYMBOLS | SPOT_METAL_SYMBOLS
    for sym in all_symbols:
        assert sym in POLYGON_TICKER_MAP, f"Missing ticker mapping for {sym}"


def test_fetch_daily_bars_rejects_unknown_symbol():
    with pytest.raises(DataSourceError, match="no Polygon ticker mapping"):
        fetch_daily_bars("ZZZZZZ", 5)


def test_fetch_daily_bars_missing_key():
    key = os.environ.pop("POLYGON_API_KEY", None)
    try:
        with pytest.raises(DataSourceError, match="POLYGON_API_KEY"):
            fetch_daily_bars("EURUSD", 5)
    finally:
        if key:
            os.environ["POLYGON_API_KEY"] = key


@pytest.mark.skipif(not os.environ.get("POLYGON_API_KEY"), reason="POLYGON_API_KEY not set")
def test_fetch_eurusd_live():
    bars = fetch_daily_bars("EURUSD", 5)
    assert isinstance(bars, list)
    if bars:
        assert "open" in bars[0]
        assert "close" in bars[0]


@pytest.mark.skipif(not os.environ.get("POLYGON_API_KEY"), reason="POLYGON_API_KEY not set")
def test_fetch_batch_live():
    result = fetch_batch(["EURUSD", "XAUUSD"], 3)
    assert "EURUSD" in result
    assert "XAUUSD" in result
