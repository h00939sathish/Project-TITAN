"""VWAP Mean Reversion strategy with execution friction modeling.

Hypothesis: Intraday price extensions beyond N standard deviation bands from Volume-Weighted Average Price
revert back to institutional fair value.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

from titan.strategies.registry import ParameterDef, StrategyRegistration, get_registry
from titan.strategies.timeframes import Timeframe


def make_vwap_signal_fn(params: dict) -> Callable[[Sequence[dict]], float]:
    """Factory for VWAP Mean Reversion signal evaluator.

    Parameters:
    - std_dev: float (standard deviation multiplier for VWAP bands, default 2.0)
    - window: int (rolling window for intraday VWAP calculation, default 30)
    """
    std_dev_mult = float(params.get("std_dev", 2.0))
    window = int(params.get("window", 30))

    def vwap_signal(bars: Sequence[dict]) -> float:
        if len(bars) < window:
            return 0.0

        sub = bars[-window:]
        cum_pv = 0.0
        cum_v = 0.0
        prices = []

        for b in sub:
            p = float(b.get("close", 0.0))
            v = float(b.get("volume", 1.0))
            if v <= 0:
                v = 1.0
            cum_pv += p * v
            cum_v += v
            prices.append(p)

        vwap = cum_pv / cum_v if cum_v > 0 else float(bars[-1].get("close", 0.0))

        # Standard deviation relative to VWAP
        variance = sum((p - vwap) ** 2 for p in prices) / len(prices)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        c_close = float(bars[-1].get("close", 0.0))
        z_score = (c_close - vwap) / std_dev

        if z_score <= -std_dev_mult:
            return 1.0  # Oversold below lower VWAP band -> BUY
        elif z_score >= std_dev_mult:
            return -1.0  # Overbought above upper VWAP band -> SELL

        return 0.0

    return vwap_signal
