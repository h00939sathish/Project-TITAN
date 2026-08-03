"""A deterministic mean-reversion strategy using z-score.

Generates BUY/SELL signals when the z-score of the close price relative
to a rolling window exceeds entry/exit thresholds.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from collections import deque
from dataclasses import dataclass, field
import statistics


@dataclass
class MeanReversion:
    """Mean-reversion strategy using z-score threshold.

    BUY when z-score < entry_z (oversold, expect bounce).
    SELL when z-score > exit_z (reverting toward mean, exit position).
    """

    window: int = 20
    entry_z: float = -2.0
    exit_z: float = -0.5

    prices: deque[float] = field(default_factory=deque)
    _in_position: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.window + 50:
            self.prices = deque(self.prices, maxlen=self.window + 50)

    def update(self, close_price: float) -> str | None:
        """Update with a new close price. Returns signal or None."""
        self.prices.append(close_price)
        if len(self.prices) < self.window + 1:
            return None

        recent = list(self.prices)[-self.window:]
        mean = statistics.mean(recent)
        std = statistics.stdev(recent) if len(recent) > 1 else 1.0
        z = (close_price - mean) / max(std, 1e-10)

        if not self._in_position and z < self.entry_z:
            self._in_position = True
            return "BUY"
        elif self._in_position and z > self.exit_z:
            self._in_position = False
            return "SELL"

        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.window + 1

