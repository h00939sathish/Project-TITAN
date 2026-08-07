"""TraderDev F1 port — EMA9 cross VWAP with trailing stop.

Candidate strategy (EXP-00025): ported from the dominant 'EMA 9 + VWAP with
ATR Trailing' family found on the trader.dev MCP server. Registered but NOT
promoted — no ``qualified_variants`` — so it can be run in the paper/replay
cycle and tested, but is never auto-selected for a live environment.

Signal logic (faithful port of the Pine v6 source):
  - EMA9 vs a running VWAP of closes (period-anchored)
  - BUY on EMA9 crossing above VWAP, SELL on crossing below
  - a trailing stop ratchets the exit level each bar

Two entry methods:
  - ``update(close_price)``   : close-only contract (backwards compatible with
    the paper bridge warmup / strategies that only forward close).
  - ``update_bar(bar)``       : full-OHLC path. When a completed bar with
    high/low arrives it is used for two things the close-only path cannot do:
    (a) a realistic rolling range for the trail distance, and (b) an intrabar
    trailing-stop check (if the bar's low/high already pierced the trail, the
    fill is treated as having happened inside that bar).

Pure calculation — no I/O, no broker/portfolio imports.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TraderDevEMA9VWAP:
    """EMA9 cross VWAP strategy with a trailing exit.

    Params:
      ema_period : fast EMA period (default 9)
      vwap_period: number of closes over which to compute the VWAP proxy
      atr_period : rolling window for the trailing stop distance
      trail_mult : trailing stop = trail_mult × range (default 3.0)
    """

    ema_period: int = 9
    vwap_period: int = 240
    atr_period: int = 14
    trail_mult: float = 3.0

    closes: deque = field(default_factory=lambda: deque(maxlen=400))
    ranges: deque = field(default_factory=lambda: deque(maxlen=60))
    _prev_ema: float | None = None
    _prev_vwap: float | None = None
    _position: int = 0          # +1 long, -1 short, 0 flat
    _trail: float | None = None  # trailing exit price (long: below, short: above)

    # make it callable like signal_fn(bar)
    def __call__(self, bar: dict) -> str | None:
        if "high" in bar and "low" in bar:
            return self.update_bar(bar)
        return self.update(float(bar["close"]))

    def _ema(self, prices: list[float], period: int) -> float:
        k = 2.0 / (period + 1)
        e = prices[0]
        for p in prices[1:]:
            e = p * k + e * (1 - k)
        return e

    def _sma(self, prices: list[float]) -> float:
        return sum(prices) / len(prices)

    def _rng(self) -> float:
        if len(self.ranges) < self.atr_period:
            return 0.0
        return self._sma(list(self.ranges)[-self.atr_period:])

    def update(self, close_price: float) -> str | None:
        """Close-only path (legacy). Processes a single close price."""
        n = len(self.closes)
        if n >= 1:
            self.ranges.append(abs(close_price - self.closes[-1]))
        self.closes.append(close_price)
        if n < max(self.vwap_period, self.ema_period + 1, self.atr_period):
            return None
        return self._decide(close_price, high=close_price, low=close_price)

    def update_bar(self, bar: dict) -> str | None:
        """Full OHLC path — uses high/low for a real range and intrabar trail."""
        close = float(bar["close"])
        high = float(bar.get("high", close))
        low = float(bar.get("low", close))
        n = len(self.closes)
        if n >= 1:
            self.ranges.append(max(high - low, abs(close - self.closes[-1])))
        self.closes.append(close)
        if n < max(self.vwap_period, self.ema_period + 1, self.atr_period):
            return None
        return self._decide(close, high=high, low=low)

    def _decide(self, close: float, high: float, low: float) -> str | None:
        closes = list(self.closes)
        ema = self._ema(closes[-self.ema_period:], self.ema_period)
        vwap = self._sma(closes[-self.vwap_period:])
        rng = self._rng()

        # intrabar trailing-stop check (real OHLC only) BEFORE new entry
        if self._position != 0 and self._trail is not None and high != low:
            if self._position > 0 and low <= self._trail:
                self._position = 0
                self._trail = None
                return "SELL"
            if self._position < 0 and high >= self._trail:
                self._position = 0
                self._trail = None
                return "BUY"

        signal = None

        # close-based trailing stop (used when no intrabar OHLC pierce above)
        if self._position != 0:
            if self._position > 0 and self._trail is not None and close <= self._trail:
                self._position = 0
                self._trail = None
                return "SELL"
            if self._position < 0 and self._trail is not None and close >= self._trail:
                self._position = 0
                self._trail = None
                return "BUY"

        # crossover detection
        if self._prev_ema is not None and self._prev_vwap is not None:
            if self._prev_ema <= self._prev_vwap and ema > vwap:
                self._position = 1
                self._trail = close - rng * self.trail_mult
                signal = "BUY"
            elif self._prev_ema >= self._prev_vwap and ema < vwap:
                self._position = -1
                self._trail = close + rng * self.trail_mult
                signal = "SELL"

        # ratchet trailing stop in the profit direction
        if self._position != 0 and self._trail is not None:
            if self._position > 0:
                self._trail = max(self._trail, close - rng * self.trail_mult)
            elif self._position < 0:
                self._trail = min(self._trail, close + rng * self.trail_mult)

        self._prev_ema = ema
        self._prev_vwap = vwap
        return signal

    @property
    def is_ready(self) -> bool:
        return len(self.closes) >= self.vwap_period