"""ADR-024 Track 1 — 1h->4h BarAggregator (strategy layer, NOT Nautilus).

Aggregates 1h completed bars into 4h bars aligned to UTC day boundaries
(00:00, 04:00, 08:00, 12:00, 16:00, 20:00) — the same alignment the research
harness's resample() uses. Pure + deterministic + testable.

Contract:
  open  = first bar's open
  high  = max of the 4 highs
  low   = min of the 4 lows
  close = last bar's close
  volume = sum of the 4 volumes
  timestamp = the 4th bar's timestamp (a 4h boundary close)

The 1h feed is unchanged; 1h strategies keep evaluating on 1h. Only the
aggregated 4h product is handed to the strategy via strategy.update_bar().
"""
from __future__ import annotations

from datetime import datetime, timezone

# UTC boundaries where a 4h bar completes
_BOUNDS = (0, 4, 8, 12, 16, 20)


def _bucket_hour(ts: datetime) -> int:
    """Return the 4h-boundary hour this timestamp belongs to (start of bucket).

    E.g. 01:00 -> 0, 05:00 -> 4, 22:00 -> 20.
    """
    return (ts.hour // 4) * 4


def _bucket_key(inst: str, ts: datetime) -> str:
    day = ts.strftime("%Y-%m-%d")
    return f"{inst}|{day}|{_bucket_hour(ts):02d}"


class BarAggregator:
    """Accumulate 1h bars per instrument and emit 4h bars on bucket close."""

    def __init__(self, target_strategy, timeframe_value: str = "4-HOUR"):
        self._target = target_strategy          # has update_bar(bar)
        self._tf_value = timeframe_value
        self._buckets: dict[str, dict] = {}

    def on_1h_bar(self, instrument_id: str, ts: datetime, o, h, l, c, v) -> list[dict]:
        """Feed one completed 1h bar. Returns a list of completed 4h bars (0 or 1)."""
        key = _bucket_key(instrument_id, ts)
        b = self._buckets.get(key)
        if b is None:
            b = {
                "instrument_id": instrument_id,
                "timestamp": ts.isoformat(),
                "open": o, "high": h, "low": l, "close": c, "volume": int(v),
                "_count": 1,
            }
            self._buckets[key] = b
        else:
            b["high"] = max(b["high"], h)
            b["low"] = min(b["low"], l)
            b["close"] = c
            b["volume"] = int(b.get("volume", 0)) + int(v)
            b["_count"] = b.get("_count", 1) + 1

        if b["_count"] < 4:
            return []
        # bucket complete -> emit
        emitted = {
            "instrument_id": instrument_id,
            "timestamp": ts.isoformat(),
            "timeframe": self._tf_value,
            "open": b["open"], "high": b["high"], "low": b["low"],
            "close": b["close"], "volume": b["volume"],
        }
        self._buckets.pop(key, None)
        return [emitted]

    def flush(self) -> list[dict]:
        """Emit any partial bucket (used on shutdown / session end)."""
        out = []
        for key, b in list(self._buckets.items()):
            if b.get("_count", 0) >= 1:
                out.append({
                    "instrument_id": b["instrument_id"],
                    "timestamp": b["timestamp"],
                    "timeframe": self._tf_value,
                    "open": b["open"], "high": b["high"], "low": b["low"],
                    "close": b["close"], "volume": b["volume"],
                })
            self._buckets.pop(key, None)
        return out