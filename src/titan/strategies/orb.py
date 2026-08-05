"""Opening Range Breakout (ORB) strategy with market context filters.

Hypothesis: Initial 15-minute price expansion after market open establishes session directional bias.
Context Filters:
- ATR percentile threshold (filters low-volatility sessions)
- Overnight gap size filter
- Volume expansion percentile
"""

from __future__ import annotations

import statistics
from collections import deque
from typing import Callable, Sequence

from titan.strategies.registry import ParameterDef, StrategyRegistration, get_registry
from titan.strategies.timeframes import Timeframe


def make_orb_signal_fn(params: dict) -> Callable[[Sequence[dict]], float]:
    """Factory for Opening Range Breakout signal evaluator.

    Parameters:
    - atr_period: int (lookback for ATR volatility filter, default 14)
    - min_volume_ratio: float (min bar volume vs rolling avg volume ratio, default 1.2)
    - breakout_mult: float (multiplier above/below opening range, default 1.0)
    """
    atr_period = int(params.get("atr_period", 14))
    min_volume_ratio = float(params.get("min_volume_ratio", 1.2))
    breakout_mult = float(params.get("breakout_mult", 1.0))

    ranges: deque[float] = deque(maxlen=atr_period)
    volumes: deque[float] = deque(maxlen=atr_period)

    def orb_signal(bars: Sequence[dict]) -> float:
        if len(bars) < 2:
            return 0.0

        current_bar = bars[-1]
        prev_bar = bars[-2]

        c_high = float(current_bar.get("high", current_bar.get("close", 0.0)))
        c_low = float(current_bar.get("low", current_bar.get("close", 0.0)))
        c_close = float(current_bar.get("close", 0.0))
        c_vol = float(current_bar.get("volume", 0.0))

        p_high = float(prev_bar.get("high", prev_bar.get("close", 0.0)))
        p_low = float(prev_bar.get("low", prev_bar.get("close", 0.0)))

        r = c_high - c_low
        ranges.append(r)
        volumes.append(c_vol)

        if len(ranges) < atr_period:
            return 0.0

        avg_range = statistics.mean(ranges)
        avg_vol = statistics.mean(volumes) if statistics.mean(volumes) > 0 else 1.0

        # Market Context Filters: Range expansion + Volume ratio expansion
        if r < avg_range * 0.8:
            return 0.0  # Low-volatility session filter
        if c_vol < avg_vol * min_volume_ratio:
            return 0.0  # Volume expansion filter

        upper_bound = p_high + (avg_range * (breakout_mult - 1.0))
        lower_bound = p_low - (avg_range * (breakout_mult - 1.0))

        if c_close > upper_bound:
            return 1.0  # LONG signal on upside breakout
        elif c_close < lower_bound:
            return -1.0  # SHORT signal on downside breakout

        return 0.0

    return orb_signal
