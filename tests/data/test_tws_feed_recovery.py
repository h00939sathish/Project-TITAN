"""Verification tests for TWS feed disconnect recovery (P0 gate).

Covers the 1100 / 10182 / farm-error storm path: recovery flag, reconnect +
resubscribe, advancing-bar verification, and the rule that CACHED prices are
NOT treated as healthy when the feed has stalled.

These are unit tests over the recovery state machine (no live TWS needed);
the feed object is built via object.__new__ to bypass the connecting __init__.
"""

import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from titan.data.tws_feed import TWSRealtimeFeed


def _bare_feed() -> TWSRealtimeFeed:
    """Construct a TWSRealtimeFeed without connecting to TWS."""
    feed = object.__new__(TWSRealtimeFeed)
    feed._instruments = ["SPY", "MSFT"]
    feed._bar_size = "5 mins"
    feed._duration = "1 D"
    feed._window = 500
    feed._host = "127.0.0.1"
    feed._port = 7497
    feed._base_cid = 150
    feed._connect_timeout = 5.0
    feed._ready = threading.Event()
    feed._lock = threading.Lock()
    feed._bars = {"SPY": [], "MSFT": []}
    feed._bars_ohlc = {"SPY": [], "MSFT": []}
    feed._forming = {"SPY": None, "MSFT": None}
    feed._forming_ohlc = {"SPY": None, "MSFT": None}
    feed._instr_by_req = {8000: "SPY", 8001: "MSFT"}
    feed._storm_codes = frozenset({1100, 2110, 2103, 2105, 2107, 2108, 10182, 10187, 10191, 202})
    feed._err_storm = 0
    feed._recovery_needed = False
    feed._recovering = False
    feed._last_update = time.monotonic()
    feed._has_any_bar = False
    return feed


class _FakeBar:
    def __init__(self, epoch: float, close: float, high: float | None = None,
                 low: float | None = None, open_: float | None = None, volume: int = 0):
        self.date = str(epoch)
        self.close = close
        self.high = high if high is not None else close
        self.low = low if low is not None else close
        self.open = open_ if open_ is not None else close
        self.volume = volume


def _push_bar(feed: TWSRealtimeFeed, req_id: int, epoch: float, close: float,
              high: float | None = None, low: float | None = None,
              open_: float | None = None, volume: int = 0) -> None:
    feed.historicalData(req_id, _FakeBar(epoch, close, high, low, open_, volume))


class TestErrorStormDetection:
    def test_lone_1100_disconnect_requests_recovery(self):
        feed = _bare_feed()
        feed.error(0, 0, 1100, "Connectivity between IBKR and Trader Workstation has been lost.")
        assert feed.needs_recovery()

    def test_10182_storm_requests_recovery(self):
        feed = _bare_feed()
        for _ in range(3):
            feed.error(0, 0, 10182, "Failed to update historical bars")
        assert feed.needs_recovery()

    def test_1102_restores_clears_storm(self):
        feed = _bare_feed()
        feed.error(0, 0, 10182, "x")
        feed.error(0, 0, 10182, "x")
        feed.error(0, 0, 1102, "Connectivity restored")
        assert feed._err_storm == 0
        assert not feed.needs_recovery()

    def test_benign_codes_do_not_trigger_recovery(self):
        feed = _bare_feed()
        feed.error(0, 0, 2158, "sec-def data farm connection is OK")
        feed.error(0, 0, 10167, "Delayed data")
        assert not feed.needs_recovery()


class TestHealthySemantics:
    def test_cached_prices_are_not_healthy_when_stalled(self):
        """Gate: cached bars must NOT be treated as healthy data."""
        feed = _bare_feed()
        # two pushes: first becomes the forming bar, second promotes it
        _push_bar(feed, 8000, 1754000000, 100.0)
        _push_bar(feed, 8000, 1754000300, 101.0)
        assert feed.is_healthy()
        # ...then the feed stalls: no updates for > stale window
        feed._last_update = time.monotonic() - 120.0
        assert feed._has_any_bar
        assert feed._bars["SPY"], "cached bar present"
        assert not feed.is_healthy(stale_after_s=30.0), "cached prices must fail closed"

    def test_no_bars_yet_is_not_stale(self):
        feed = _bare_feed()
        feed._last_update = time.monotonic() - 3600.0
        assert feed.is_healthy(stale_after_s=30.0)  # pre-warmup, nothing to judge

    def test_fresh_updates_are_healthy(self):
        feed = _bare_feed()
        _push_bar(feed, 8000, time.time(), 100.0)
        assert feed.is_healthy(stale_after_s=30.0)

    def test_recovering_is_unhealthy(self):
        feed = _bare_feed()
        feed._recovering = True
        assert not feed.is_healthy()


class TestHistorical:
    def test_historical_data_tracks_update_time(self):
        feed = _bare_feed()
        before = feed._last_update
        _push_bar(feed, 8000, time.time(), 100.0)
        assert feed._last_update >= before
        assert feed._has_any_bar


class TestFullOHLC:
    def test_completed_ohlc_captures_high_low_open(self):
        feed = _bare_feed()
        _push_bar(feed, 8000, 1754000000, 100.0, high=102.0, low=99.0, open_=101.0, volume=55)
        _push_bar(feed, 8000, 1754000300, 101.0, high=103.0, low=100.5, open_=100.0, volume=60)
        ohlc = feed.completed_ohlc("SPY")
        assert len(ohlc) == 1, "only the completed bar is exposed"
        b = ohlc[0]
        assert b["open"] == 101.0
        assert b["high"] == 102.0
        assert b["low"] == 99.0
        assert b["close"] == 100.0
        assert b["volume"] == 55
        assert b["timestamp"] == "2025-07-31T22:13:20Z"

    def test_completed_ohlc_mirrors_completed_bars(self):
        feed = _bare_feed()
        for e, c in [(1754000000, 100.0), (1754000300, 101.0)]:
            _push_bar(feed, 8000, e, c, high=c + 1, low=c - 1, open_=c, volume=10)
        assert len(feed.completed_bars("SPY")) == len(feed.completed_ohlc("SPY")) == 1
        assert feed.completed_bars("SPY")[0][1] == feed.completed_ohlc("SPY")[0]["close"]

    def test_latest_completed_ohlc(self):
        feed = _bare_feed()
        _push_bar(feed, 8000, 1754000000, 100.0, high=101.0, low=99.0, open_=99.5, volume=5)
        _push_bar(feed, 8000, 1754000300, 101.0, high=102.0, low=100.0, open_=100.5, volume=6)
        latest = feed.latest_completed_ohlc("SPY")
        assert latest is not None, "a completed ohlc bar exists"
        assert latest["close"] == 100.0
class TestRecover:
    def test_recover_reconnects_and_resubscribes(self):
        feed = _bare_feed()
        feed.connect = MagicMock()
        feed.disconnect = MagicMock()
        feed.run = MagicMock()
        feed._subscribe = MagicMock()
        feed._recovery_needed = True
        feed._err_storm = 3

        # nextValidId will be delivered on the client thread; simulate it.
        def _fake_connect(host, port, cid):
            feed._ready.set()

        feed.connect.side_effect = _fake_connect
        feed.recover()

        feed.disconnect.assert_called_once()
        assert feed.connect.called
        feed._subscribe.assert_called_once()  # resubscribed all contracts
        assert not feed.needs_recovery()
        assert not feed._recovering
        assert feed._err_storm == 0

    def test_recover_keeps_completed_bars(self):
        feed = _bare_feed()
        _push_bar(feed, 8000, 1754000000, 100.0)
        _push_bar(feed, 8000, 1754000300, 101.0)  # one completed bar
        feed.connect = MagicMock(side_effect=lambda h, p, c: feed._ready.set())
        feed.disconnect = MagicMock()
        feed.run = MagicMock()
        feed._subscribe = MagicMock()
        feed.recover()
        assert len(feed._bars["SPY"]) == 1, "completed bars survive recovery"
        assert feed._forming["SPY"] is None, "forming bar resets for fresh promotion"
