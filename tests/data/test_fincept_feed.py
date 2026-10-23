"""Tests for FinceptDataFeed (Two-tier market data integration & safety guardrails)."""

from datetime import datetime, timezone
import pytest

from titan.data.fincept_feed import (
    DataTier,
    ExecutionSafetyViolation,
    FinceptBar,
    FinceptDataFeed,
)
from titan.data.approved import DataSourceError
from titan.strategies.timeframes import Timeframe


class MockMarketData:
    def get_quote(self, symbol: str):
        class Quote:
            bid = 1450.25
            ask = 1450.50
            last = 1450.35
            volume = 250000.0
        return Quote()

    def get_latest_bar(self, symbol: str, timeframe: str):
        class Bar:
            timestamp = "2026-09-22T10:00:00+00:00"
            open = 1445.0
            high = 1455.0
            low = 1440.0
            close = 1450.35
            volume = 12000.0
        return Bar()


class MockDataHub:
    def get_history(self, symbol: str, timeframe: str, limit: int):
        bars = []
        for i in range(limit):
            class HistBar:
                timestamp = f"2026-09-{i+1:02d}T10:00:00+00:00"
                open = 1400.0 + i
                high = 1410.0 + i
                low = 1395.0 + i
                close = 1405.0 + i
                volume = 50000.0
            bars.append(HistBar())
        return bars


class MockFinceptNative:
    market_data = MockMarketData()
    datahub = MockDataHub()


def test_feed_initialization_offline():
    feed = FinceptDataFeed(native_module=None, default_exchange="NSE")
    assert not feed.is_native_available
    assert feed.default_exchange == "NSE"


def test_tier_1_live_quote_and_bar():
    feed = FinceptDataFeed()
    quote = feed.fetch_live_quote("INFY")
    assert quote["symbol"] == "INFY"
    assert quote["tier"] == DataTier.TIER_1_LIVE.value
    assert quote["last"] > 0

    bar = feed.fetch_live_bar("INFY", timeframe=Timeframe.FIVE_MINUTES)
    assert bar.symbol == "INFY"
    assert bar.tier == DataTier.TIER_1_LIVE
    assert bar.close > 0


def test_bar_to_canonical_market_event():
    feed = FinceptDataFeed()
    bar = feed.fetch_live_bar("INFY", timeframe=Timeframe.FIVE_MINUTES)
    event = bar.to_market_event(timeframe=Timeframe.FIVE_MINUTES, counter=42)

    assert event.source == "fincept_terminal"
    assert event.event_type == "BarClosed"
    assert event.instrument_id == "INFY"
    assert event.payload["timeframe"] == "5m"
    assert event.payload["tier"] == DataTier.TIER_1_LIVE.value
    assert len(event.payload_digest) == 64  # SHA256 hex digest


def test_tier_2_historical_bars():
    feed = FinceptDataFeed()
    bars = feed.fetch_historical_bars("INFY", timeframe=Timeframe.ONE_DAY, limit=10)
    assert len(bars) == 10
    for b in bars:
        assert b.symbol == "INFY"
        assert b.tier == DataTier.TIER_2_DATAHUB  # Flagged as Tier 2


def test_tier_2_macro_indicators():
    feed = FinceptDataFeed()
    vix = feed.fetch_macro_indicator("VIX")
    assert vix["indicator"] == "VIX"
    assert vix["value"] > 0
    assert vix["tier"] == DataTier.TIER_2_DATAHUB.value

    treasury = feed.fetch_macro_indicator("TREASURY_10Y")
    assert treasury["indicator"] == "TREASURY_10Y"
    assert treasury["value"] > 0

    with pytest.raises(DataSourceError):
        feed.fetch_macro_indicator("INVALID_UNKNOWN_MACRO")


def test_universe_screening():
    feed = FinceptDataFeed()
    # Default fallback quotes have last=100.02, volume=1000.0
    # High threshold should filter everything out
    empty_screen = feed.screen_universe(min_price=200.0, min_volume=10000.0)
    assert len(empty_screen) == 0

    # Normal threshold should include candidates
    screened = feed.screen_universe(min_price=10.0, min_volume=500.0, candidates=["INFY", "TCS"])
    assert "INFY" in screened
    assert "TCS" in screened


def test_safety_guardrail_enforcement():
    tier1_bar = FinceptBar(
        symbol="INFY",
        timestamp="2026-09-22T10:00:00+00:00",
        open=1400.0,
        high=1410.0,
        low=1390.0,
        close=1405.0,
        volume=1000.0,
        tier=DataTier.TIER_1_LIVE,
    )
    # Tier 1 passes safety gate
    FinceptDataFeed.validate_for_execution(tier1_bar)

    tier2_bar = FinceptBar(
        symbol="INFY",
        timestamp="2026-09-22T10:00:00+00:00",
        open=1400.0,
        high=1410.0,
        low=1390.0,
        close=1405.0,
        volume=1000.0,
        tier=DataTier.TIER_2_DATAHUB,
    )
    # Tier 2 MUST raise ExecutionSafetyViolation
    with pytest.raises(ExecutionSafetyViolation) as exc_info:
        FinceptDataFeed.validate_for_execution(tier2_bar)
    assert "Execution Safety Gate tripped" in str(exc_info.value)


def test_feed_health():
    feed = FinceptDataFeed()
    feed.fetch_live_bar("INFY")

    # INFY is covered
    verdict = feed.feed_health(["INFY"])
    assert verdict.healthy
    assert verdict.reason == ""

    # RELIANCE was not fetched -> uncovered
    uncovered_verdict = feed.feed_health(["INFY", "RELIANCE"])
    assert not uncovered_verdict.healthy
    assert uncovered_verdict.reason == "instrument_uncovered"


def test_with_mock_native_module():
    mock_native = MockFinceptNative()
    feed = FinceptDataFeed(native_module=mock_native)
    assert feed.is_native_available

    quote = feed.fetch_live_quote("INFY")
    assert quote["bid"] == 1450.25
    assert quote["ask"] == 1450.50

    bar = feed.fetch_live_bar("INFY")
    assert bar.close == 1450.35

    hist_bars = feed.fetch_historical_bars("INFY", limit=5)
    assert len(hist_bars) == 5
    assert hist_bars[0].tier == DataTier.TIER_2_DATAHUB
