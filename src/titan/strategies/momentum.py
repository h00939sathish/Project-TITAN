"""A time-series momentum strategy.

BUY/SELL based on the sign of the N-day return.
Goes LONG when return is positive, SHORT when negative.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from collections import deque
from dataclasses import dataclass, field


@dataclass
class TimeSeriesMomentum:
    """Time-series momentum (trend-following).

    BUY (enter long) when the N-day return is positive.
    SELL (enter short) when the N-day return is negative.
    Direction reverses on sign change.
    """

    lookback: int = 20

    prices: deque[float] = field(default_factory=deque)
    _position: str = "FLAT"

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.lookback + 50:
            self.prices = deque(self.prices, maxlen=self.lookback + 50)

    def update(self, close_price: float) -> str | None:
        self.prices.append(close_price)
        if not self.is_ready:
            return None

        n_day_return = (
            self.prices[-1] - self.prices[-(self.lookback + 1)]
        ) / self.prices[-(self.lookback + 1)]

        if n_day_return > 0:
            if self._position == "SHORT":
                self._position = "FLAT"
                return "BUY"
            if self._position == "FLAT":
                self._position = "LONG"
                return "BUY"
        elif n_day_return < 0:
            if self._position == "LONG":
                self._position = "FLAT"
                return "SELL"
            if self._position == "FLAT":
                self._position = "SHORT"
                return "SELL"

        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.lookback + 1

