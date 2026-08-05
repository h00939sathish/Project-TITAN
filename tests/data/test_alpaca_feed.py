"""Tests for AlpacaDataFeed."""

import os
import pytest
from unittest.mock import patch

from titan.data.alpaca_feed import AlpacaDataFeed, AlpacaBar
from titan.data.approved import DataSourceError


class TestAlpacaBar:
    def test_to_dict(self):
        bar = AlpacaBar("SPY", "2026-01-10T14:30:00Z", 100.0, 101.0, 99.0, 100.5, 1000000.0)
        d = bar.to_dict()
        assert d["instrument_id"] == "SPY"
        assert d["timestamp"] == "2026-01-10T14:30:00Z"
        assert d["open"] == 100.0
        assert d["close"] == 100.5
        assert d["volume"] == 1000000.0


class TestAlpacaDataFeedBase:
    def test_no_credentials_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(DataSourceError, match="not configured"):
                AlpacaDataFeed()

    def test_partial_credentials_raises(self):
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "key"}, clear=True):
            with pytest.raises(DataSourceError, match="not configured"):
                AlpacaDataFeed()


@pytest.mark.skip(reason="requires Alpaca paper credentials with data API access")
class TestAlpacaDataFeedIntegration:
    def test_fetch_daily_bars_spy(self):
        feed = AlpacaDataFeed(paper=True)
        bars = feed.fetch_daily_bars("SPY", limit=5)
        assert len(bars) > 0
        assert all(b.symbol == "SPY" for b in bars)
        assert all(b.open > 0 for b in bars)

    def test_fetch_to_approved_format(self):
        feed = AlpacaDataFeed(paper=True)
        result = feed.fetch_to_approved("SPY", days=5)
        assert len(result) > 0
        assert "instrument_id" in result[0]
        assert "close" in result[0]

    def test_fetch_invalid_symbol(self):
        feed = AlpacaDataFeed(paper=True)
        with pytest.raises(DataSourceError, match="not in ALLOWED_SYMBOLS"):
            feed.fetch_daily_bars("INVALID", limit=1)

    def test_fetch_multi_instrument(self):
        feed = AlpacaDataFeed(paper=True)
        spy = feed.fetch_daily_bars("SPY", limit=3)
        qqq = feed.fetch_daily_bars("QQQ", limit=3)
        assert all(b.symbol == "SPY" for b in spy)
        assert all(b.symbol == "QQQ" for b in qqq)
