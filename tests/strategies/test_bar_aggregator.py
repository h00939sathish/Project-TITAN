"""ADR-024 Track 1 tests — 1h->4h BarAggregator correctness and boundary
alignment, matching the research harness's resample() semantics."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from titan.strategies.bar_aggregator import BarAggregator, _bucket_hour


def _ts(hour, minute=0):
    return datetime(2026, 8, 3, hour, minute, tzinfo=timezone.utc)


def _h(hour):
    return _ts(hour)


class TestBucketHour:
    def test_bounding_boundaries(self):
        assert _bucket_hour(_h(1)) == 0
        assert _bucket_hour(_h(3)) == 0
        assert _bucket_hour(_h(4)) == 4
        assert _bucket_hour(_h(7)) == 4
        assert _bucket_hour(_h(22)) == 20
        assert _bucket_hour(_h(23)) == 20


class TestAggregation:
    def test_close_only_after_four_bars(self):
        a = BarAggregator(object())
        emitted = []
        for hh in range(4):
            r = a.on_1h_bar("EURUSD", _h(hh), 1.0, 1.01, 0.99, 1.005, 100)
            emitted += r
        assert emitted, "a full 4-bar bucket must emit exactly one 4h bar"
        assert len(emitted) == 1
        assert emitted[0]["timeframe"] == "4-HOUR"

    def test_open_high_low_close_volume_math(self):
        a = BarAggregator(object())
        # 4 1h bars: opens 1.00-1.03, high/low envelope, closes rising
        bars = [
            (1.0000, 1.0020, 0.9990, 1.0010, 10),
            (1.0010, 1.0030, 1.0005, 1.0020, 20),
            (1.0020, 1.0050, 1.0010, 1.0040, 30),
            (1.0040, 1.0060, 1.0030, 1.0055, 40),
        ]
        emitted = []
        for i, (o, h, l, c, v) in enumerate(bars):
            emitted += a.on_1h_bar("GBPUSD", _h(i), o, h, l, c, v)
        bar = emitted[0]
        assert bar["open"] == 1.0000          # first bar's open
        assert bar["high"] == 1.0060          # max high
        assert bar["low"] == 0.9990           # min low (bar 0)
        assert bar["close"] == 1.0055         # last bar's close
        assert bar["volume"] == 100           # sum of volumes

    def test_bucket_does_not_emit_at_three_bars(self):
        a = BarAggregator(object())
        emitted = []
        for i in range(3):
            emitted += a.on_1h_bar("EURUSD", _h(i), 1.0, 1.0, 1.0, 1.0, 100)
        assert emitted == []

    def test_non_contiguous_hours_still_bucket_by_boundary(self):
        # bars at 01:00, 02:00, 03:00, and 04:00 -> first 3 in the 00 bucket,
        # the 04:00 bar starts a NEW bucket (different boundary).
        a = BarAggregator(object())
        e0 = a.on_1h_bar("EURUSD", _h(1), 1.0, 1.0, 1.0, 1.0, 1)
        e1 = a.on_1h_bar("EURUSD", _h(2), 1.0, 1.0, 1.0, 1.0, 1)
        e2 = a.on_1h_bar("EURUSD", _h(3), 1.0, 1.0, 1.0, 1.0, 1)
        assert not (e0 or e1 or e2)
        e3 = a.on_1h_bar("EURUSD", _h(4), 1.0, 1.0, 1.0, 1.0, 1)  # new bucket
        assert e3 == []  # bucket 0 still lacks its 4th bar (only had 3)
        # add one more 00,ch bar to close bucket0? Not needed — assert flush
        out = a.flush()
        assert any(b["instrument_id"] == "EURUSD" for b in out)

    def test_flush_emits_partial_bucket(self):
        a = BarAggregator(object())
        a.on_1h_bar("EURUSD", _h(0), 1.0, 1.1, 0.9, 1.05, 25)
        a.on_1h_bar("EURUSD", _h(1), 1.05, 1.15, 1.0, 1.10, 25)
        out = a.flush()
        assert len(out) == 1
        assert out[0]["open"] == 1.0
        assert out[0]["close"] == 1.10
        assert out[0]["volume"] == 50

    def test_instrument_isolation(self):
        a = BarAggregator(object())
        a.on_1h_bar("EURUSD", _h(0), 1.0, 1.0, 1.0, 1.0, 1)
        # feed GBPUSD in the same bucket hour — must NOT share EURUSD's bucket
        a.on_1h_bar("GBPUSD", _h(0), 2.0, 2.0, 2.0, 2.0, 1)
        out = a.flush()
        assert len(out) == 2
        assert {b["instrument_id"] for b in out} == {"EURUSD", "GBPUSD"}