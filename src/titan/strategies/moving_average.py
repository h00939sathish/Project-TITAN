"""A deterministic moving-average crossover strategy.

Generates BUY/SELL signals when fast MA crosses above/below slow MA.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from dataclasses import dataclass, field


@dataclass
class MovingAverageCrossover:
    """Simple moving average crossover strategy."""

    fast_period: int = 5
    slow_period: int = 20

    prices: list[float] = field(default_factory=list)

    def update(self, close_price: float) -> str | None:
        """Update with a new close price. Returns signal or None."""
        self.prices.append(close_price)
        if len(self.prices) < self.slow_period + 1:
            return None

        fast_ma = sum(self.prices[-self.fast_period:]) / self.fast_period
        slow_ma = sum(self.prices[-self.slow_period:]) / self.slow_period

        # Check for crossover
        if len(self.prices) >= self.slow_period + 2:
            prev_fast = sum(self.prices[-(self.fast_period + 1):-1]) / self.fast_period
            prev_slow = sum(self.prices[-(self.slow_period + 1):-1]) / self.slow_period

            if prev_fast <= prev_slow and fast_ma > slow_ma:
                return "BUY"
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                return "SELL"

        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.slow_period
