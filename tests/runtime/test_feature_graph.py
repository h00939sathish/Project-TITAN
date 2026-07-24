import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from titan.runtime.events import MarketEvent
from titan.runtime.feature_graph import BarSnapshot, FeatureGraph, SourceConsistencyError
from titan.strategies.timeframes import Timeframe


@pytest.fixture
def graph():
    return FeatureGraph()


@pytest.fixture
def event_factory():
    class _Factory:
        _counter = 0

        def tick(self, instrument_id: str = "SPY", price: float = 100.0, timestamp=None):
            self._counter += 1
            ts = timestamp or datetime.now(timezone.utc)
            payload = {"price": price, "timestamp": ts.isoformat()}
            return MarketEvent(
                message_id=f"tick-{self._counter}",
                causation_id=f"cause-{self._counter}",
                correlation_id=f"corr-{self._counter}",
                occurred_at=ts,
                received_at=ts,
                schema_version=1,
                source="test",
                event_type="Tick",
                instrument_id=instrument_id,
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

        def external_bar(self, instrument_id: str = "SPY", timeframe: Timeframe = Timeframe.FIVE_MINUTES, close: float = 100.0):
            self._counter += 1
            now = datetime.now(timezone.utc)
            payload = {
                "timeframe": timeframe,
                "close": close,
                "instrument_id": instrument_id,
                "source": "external",
            }
            return MarketEvent(
                message_id=f"ext-bar-{self._counter}",
                causation_id=f"cause-{self._counter}",
                correlation_id=f"corr-{self._counter}",
                occurred_at=now,
                received_at=now,
                schema_version=1,
                source="external",
                event_type="BarClosed",
                instrument_id=instrument_id,
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

        def bar_closed(self, timeframe: Timeframe, instrument_id: str = "SPY", close: float = 100.0, timestamp=None):
            self._counter += 1
            ts = timestamp or datetime.now(timezone.utc)
            payload = {
                "timeframe": timeframe,
                "close": close,
                "instrument_id": instrument_id,
            }
            return MarketEvent(
                message_id=f"bar-{self._counter}",
                causation_id=f"cause-{self._counter}",
                correlation_id=f"corr-{self._counter}",
                occurred_at=ts,
                received_at=ts,
                schema_version=1,
                source="test",
                event_type="BarClosed",
                instrument_id=instrument_id,
                payload=payload,
                payload_digest=hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            )

    return _Factory()


@pytest.fixture
def ticks():
    class _Tick:
        def __init__(self, price, timestamp, instrument_id="SPY"):
            self.price = price
            self.timestamp = timestamp
            self.instrument_id = instrument_id

        def to_market_event(self):
            payload = {"price": self.price, "timestamp": self.timestamp.isoformat()}
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            return MarketEvent(
                message_id=f"tick-{id(self)}",
                causation_id="cause-tick",
                correlation_id="corr-tick",
                occurred_at=self.timestamp,
                received_at=self.timestamp,
                schema_version=1,
                source="test",
                event_type="Tick",
                instrument_id=self.instrument_id,
                payload=payload,
                payload_digest=digest,
            )

    class _Ticks:
        def for_minutes(self, n, start_price=100.0, instrument_id="SPY"):
            base = datetime(2026, 7, 24, 9, 30, tzinfo=timezone.utc)
            items = []
            for i in range(n):
                ts = base + timedelta(minutes=i)
                items.append(_Tick(start_price + i, ts, instrument_id))
            self._items = items
            return items

        def __getitem__(self, i):
            return self._items[i]

    return _Ticks()


def test_ticks_derive_stable_five_minute_then_hourly_bars(graph, ticks):
    seq = ticks.for_minutes(60)
    for tick in seq:
        graph.on_market_event(tick.to_market_event())

    b5 = graph.bar("SPY", Timeframe.FIVE_MINUTES, 0)
    assert b5 is not None
    assert b5.close == seq[-1].price

    b1 = graph.bar("SPY", Timeframe.ONE_HOUR, 0)
    assert b1 is not None
    assert b1.close == seq[-1].price


def test_graph_rejects_mixed_external_and_derived_sources(graph, event_factory):
    graph.on_market_event(event_factory.tick("SPY", 100.0))
    with pytest.raises(SourceConsistencyError):
        graph.on_market_event(event_factory.external_bar("SPY", Timeframe.FIVE_MINUTES))


def test_one_minute_from_ticks(graph, ticks):
    seq = ticks.for_minutes(3, start_price=100.0)
    for tick in seq:
        graph.on_market_event(tick.to_market_event())

    b = graph.bar("SPY", Timeframe.ONE_MINUTE, 0)
    assert b is not None
    assert b.open == seq[-1].price
    assert b.close == seq[-1].price


def test_empty_graph_returns_none(graph):
    assert graph.bar("SPY", Timeframe.FIVE_MINUTES, 0) is None
    assert graph.bar("SPY", Timeframe.ONE_HOUR, 0) is None
    assert graph.bar("SPY", Timeframe.ONE_DAY, 0) is None


def test_graph_digest_replay(graph, ticks):
    seq = ticks.for_minutes(10, start_price=100.0)
    for tick in seq:
        graph.on_market_event(tick.to_market_event())

    bars_a = [graph.bar("SPY", Timeframe.FIVE_MINUTES, i) for i in range(2)]

    g2 = FeatureGraph()
    for tick in seq:
        g2.on_market_event(tick.to_market_event())
    bars_b = [g2.bar("SPY", Timeframe.FIVE_MINUTES, i) for i in range(2)]

    for a, b in zip(bars_a, bars_b):
        assert a.open == b.open
        assert a.high == b.high
        assert a.low == b.low
        assert a.close == b.close


def test_missing_source_marks_dependent_stale(graph, ticks):
    seq = ticks.for_minutes(3, start_price=100.0)
    for tick in seq:
        graph.on_market_event(tick.to_market_event())

    assert graph.bar("SPY", Timeframe.FIVE_MINUTES, 0) is None
    assert graph.bar("SPY", Timeframe.ONE_HOUR, 0) is None


def test_bar_rejects_mixed_source_tick_then_bar(graph, event_factory):
    graph.on_market_event(event_factory.bar_closed(Timeframe.FIVE_MINUTES, close=100.0))
    with pytest.raises(SourceConsistencyError):
        graph.on_market_event(event_factory.tick("SPY", 101.0))


def test_five_minute_ohlc_aggregation(graph, ticks):
    seq = ticks.for_minutes(10, start_price=100.0)
    for tick in seq:
        graph.on_market_event(tick.to_market_event())

    b0 = graph.bar("SPY", Timeframe.FIVE_MINUTES, 1)
    assert b0 is not None
    assert b0.open == 100.0
    assert b0.high == 104.0
    assert b0.low == 100.0
    assert b0.close == 104.0

    b1 = graph.bar("SPY", Timeframe.FIVE_MINUTES, 0)
    assert b1 is not None
    assert b1.open == 105.0
    assert b1.high == 109.0
    assert b1.low == 105.0
    assert b1.close == 109.0


def test_different_instruments_isolated(graph, event_factory):
    graph.on_market_event(event_factory.tick("SPY", 100.0))
    graph.on_market_event(event_factory.tick("QQQ", 200.0))
    assert graph.bar("SPY", Timeframe.ONE_MINUTE, 0) is not None
    assert graph.bar("QQQ", Timeframe.ONE_MINUTE, 0) is not None
