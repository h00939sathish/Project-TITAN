"""Reusable pre-signal filters — multi-timeframe confirmation, volatility gate, etc.

Each filter is a callable that receives the current price and optional
higher-timeframe data, and returns True (allow) or False (suppress).
"""

import statistics
from abc import ABC, abstractmethod


class SignalFilter(ABC):
    @abstractmethod
    def check(self, price: float, htf_prices: list[float] | None = None) -> bool:
        ...


def _compute_ema(prices: list[float], period: int) -> float:
    if len(prices) < period:
        return statistics.mean(prices) if prices else 0.0
    k = 2.0 / (period + 1.0)
    ema = statistics.mean(prices[:period])
    for p in prices[period:]:
        ema = (p * k) + (ema * (1.0 - k))
    return ema


class WeeklyTrendFilter(SignalFilter):
    """Only allow signals when weekly trend agrees.

    Computes fast and slow EMA over the higher-timeframe price series.
    Default: weekly EMA50 > EMA200 = bullish.
    """

    def __init__(self, fast: int = 5, slow: int = 20, require_bullish: bool = True):
        self.fast = fast
        self.slow = slow
        self.require_bullish = require_bullish

    def check(self, price: float, htf_prices: list[float] | None = None) -> bool:
        if not htf_prices or len(htf_prices) < self.slow:
            return True
        fast_ema = _compute_ema(htf_prices, self.fast)
        slow_ema = _compute_ema(htf_prices, self.slow)
        bullish = fast_ema > slow_ema
        return bullish if self.require_bullish else not bullish



class VolatilityFilter(SignalFilter):
    """Suppress signals when short-term vol exceeds threshold relative to long-term vol."""

    def __init__(self, vol_window: int = 14, median_window: int = 60, max_vol_ratio: float = 2.0):
        self.vol_window = vol_window
        self.median_window = median_window
        self.max_vol_ratio = max_vol_ratio
        self._closes: list[float] = []

    def check(self, price: float, htf_prices: list[float] | None = None) -> bool:
        self._closes.append(price)
        if len(self._closes) < self.median_window + 1:
            return True
        recent = self._closes[-self.vol_window:]
        lookback = self._closes[-self.median_window:]
        current_vol = statistics.stdev(
            [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent))]
        ) if len(recent) > 1 else 0.0
        hist_vols = []
        for i in range(1, len(lookback) - self.vol_window + 1):
            seg = lookback[i:i + self.vol_window]
            h = statistics.stdev([(seg[j] - seg[j - 1]) / seg[j - 1] for j in range(1, len(seg))])
            hist_vols.append(h)
        median_vol = statistics.median(hist_vols) if hist_vols else current_vol
        if median_vol < 1e-10:
            return True
        return (current_vol / median_vol) <= self.max_vol_ratio
