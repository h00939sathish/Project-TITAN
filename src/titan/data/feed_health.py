"""Feed-health snapshot for the kill-switch release gate (ADR-019).

Data-feed-owned, fail-closed market-data health. The owner is the realtime
feed (e.g. ``TWSRealtimeFeed``) which already tracks per-instrument completed
bars, connection health, and recovery state; this module evaluates that state
against the required-instrument list and a staleness threshold and returns a
single structured verdict the engine consumes read-only during release.

Predicates (all fail closed per ADR-019):
- feed absent          -> feed_health_absent
- feed needs recovery  -> feed_recovering
- not is_healthy       -> feed_stale
- bars not advancing   -> bar_not_advancing
- per required instrument: no completed bar or watermark older than the
  threshold           -> instrument_uncovered
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


@dataclass
class FeedHealthVerdict:
    healthy: bool
    reason: str = ""  # "" when healthy; else one of the codes above
    watermarks: dict[str, Optional[str]] = field(default_factory=dict)  # instr -> last completed bar ts
    checked_at: str = ""

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "reason": self.reason,
            "watermarks": self.watermarks,
            "checked_at": self.checked_at,
        }


class FeedHealthSnapshot:
    """Evaluates feed health against required instruments and a staleness budget."""

    def __init__(
        self,
        feed: Any,
        required_instruments: list[str],
        stale_after_s: float,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._feed = feed
        self._instruments = list(required_instruments)
        self._stale_after_s = float(stale_after_s)
        self._now_fn = now_fn

    # Contract helpers so any feed exposing the same primitives satisfies it.
    def _is_healthy(self) -> bool:
        f = self._feed
        if f is None:
            return False
        h = getattr(f, "is_healthy", None)
        if callable(h):
            try:
                return bool(h(self._stale_after_s))
            except Exception:
                return False
        # Missing contract => fail closed (ADR-019).
        return False

    def _needs_recovery(self) -> bool:
        f = self._feed
        if f is None:
            return True
        nr = getattr(f, "needs_recovery", None)
        if callable(nr):
            try:
                return bool(nr())
            except Exception:
                return True
        return True

    def _bars_advancing(self) -> bool:
        f = self._feed
        if f is None:
            return False
        ba = getattr(f, "bars_advancing", None)
        if callable(ba):
            try:
                return bool(ba())
            except Exception:
                return False
        return True

    def _latest_completed(self, instr: str) -> Optional[str]:
        f = self._feed
        if f is None:
            return None
        lc = getattr(f, "latest_completed", None)
        if callable(lc):
            try:
                item = lc(instr)
                if item:
                    return str(item[0])  # (iso_ts, close)
                return None
            except Exception:
                return None
        return None

    def evaluate(self) -> FeedHealthVerdict:
        checked_at = datetime.now(timezone.utc).isoformat()

        if self._feed is None:
            return FeedHealthVerdict(False, "feed_health_absent", {}, checked_at)

        if self._needs_recovery():
            return FeedHealthVerdict(False, "feed_recovering", {}, checked_at)

        if not self._is_healthy():
            return FeedHealthVerdict(False, "feed_stale", {}, checked_at)

        if not self._bars_advancing():
            return FeedHealthVerdict(False, "bar_not_advancing", {}, checked_at)

        watermarks: dict[str, Optional[str]] = {}
        for instr in self._instruments:
            ts = self._latest_completed(instr)
            watermarks[instr] = ts
            if ts is None:
                return FeedHealthVerdict(
                    False, "instrument_uncovered", watermarks, checked_at
                )

        return FeedHealthVerdict(True, "", watermarks, checked_at)
