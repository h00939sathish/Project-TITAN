"""Bollinger Band mean-reversion strategy.

BUY when price closes below the lower band,
SELL when price closes back above the middle band.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import statistics


@dataclass
class BollingerBands:
    """Bollinger Band mean-reversion strategy.

    BUY when close <= lower band after warmup.
    SELL when close >= middle band while in position.
    """

    window: int = 20
    std_dev_multiplier: float = 2.5

    prices: deque[float] = field(default_factory=deque)
    _in_position: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.window + 50:
            self.prices = deque(self.prices, maxlen=self.window + 50)

    def update(self, close_price: float) -> str | None:
        self.prices.append(close_price)
        if len(self.prices) < self.window:
            return None

        window = list(self.prices)[-self.window:]
        mid = statistics.mean(window)
        std = statistics.stdev(window) if len(window) > 1 else 0.0
        band = self.std_dev_multiplier * std
        lower = mid - band

        if not self._in_position and close_price <= lower:
            self._in_position = True
            return "BUY"
        if self._in_position and close_price >= mid:
            self._in_position = False
            return "SELL"
        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.window

