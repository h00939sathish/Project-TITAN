"""A deterministic moving-average crossover strategy.

Generates BUY/SELL signals when fast MA crosses above/below slow MA.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class MovingAverageCrossover:
    """Simple moving average crossover strategy."""

    fast_period: int = 5
    slow_period: int = 20

    prices: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.slow_period + 50:
            self.prices = deque(self.prices, maxlen=self.slow_period + 50)

    def update(self, close_price: float) -> str | None:
        """Update with a new close price. Returns signal or None."""
        self.prices.append(close_price)
        if len(self.prices) < self.slow_period:
            return None

        recent_prices = list(self.prices)
        fast_ma = sum(recent_prices[-self.fast_period:]) / self.fast_period
        slow_ma = sum(recent_prices[-self.slow_period:]) / self.slow_period

        # Check for crossover
        if len(recent_prices) >= self.slow_period + 1:
            prev_fast = sum(recent_prices[-(self.fast_period + 1):-1]) / self.fast_period
            prev_slow = sum(recent_prices[-(self.slow_period + 1):-1]) / self.slow_period

            if prev_fast <= prev_slow and fast_ma > slow_ma:
                return "BUY"
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                return "SELL"

        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.slow_period

