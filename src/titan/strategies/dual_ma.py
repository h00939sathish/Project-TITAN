"""A dual-direction moving-average strategy — always in the market.

Long when fast MA > slow MA, short when fast MA < slow MA.
Signals on every bar after warmup (no flat periods).
"""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class DualMovingAverage:
    fast_period: int = 5
    slow_period: int = 20
    prices: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.slow_period + 50:
            self.prices = deque(self.prices, maxlen=self.slow_period + 50)

    def update(self, close_price: float) -> str | None:
        self.prices.append(close_price)
        if len(self.prices) < self.slow_period:
            return None
        recent_fast = list(self.prices)[-self.fast_period:]
        recent_slow = list(self.prices)[-self.slow_period:]
        fast_ma = sum(recent_fast) / self.fast_period
        slow_ma = sum(recent_slow) / self.slow_period
        return "BUY" if fast_ma > slow_ma else "SELL"

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.slow_period

