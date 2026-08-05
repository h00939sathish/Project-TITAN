"""A volatility-regime timing strategy.

BUY/SELL based on whether short-term volatility is below or above
its longer-term median — a regime-awareness strategy, not price-directional.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from collections import deque
from dataclasses import dataclass, field
import statistics


@dataclass
class VolatilityRegime:
    """Volatility-regime timing.

    BUY when rolling vol drops below median_vol * vol_multiple (low-vol regime).
    SELL when rolling vol rises above median_vol * vol_multiple (high-vol regime).
    """

    vol_window: int = 20
    median_window: int = 60
    vol_multiple: float = 1.0

    closes: deque[float] = field(default_factory=deque)
    vols: deque[float] = field(default_factory=deque)
    _in_position: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.closes, deque) or self.closes.maxlen != self.vol_window + 5:
            self.closes = deque(self.closes, maxlen=self.vol_window + 5)
        if not isinstance(self.vols, deque) or self.vols.maxlen != self.median_window:
            self.vols = deque(self.vols, maxlen=self.median_window)

    def update(self, close_price: float) -> str | None:
        self.closes.append(close_price)
        if len(self.closes) < self.vol_window + 1:
            return None

        recent_closes = list(self.closes)
        returns = [
            (recent_closes[i] - recent_closes[i - 1]) / recent_closes[i - 1]
            for i in range(1, len(recent_closes))
        ]
        vol = statistics.stdev(returns) if len(returns) > 1 else 0.0
        self.vols.append(vol)

        if len(self.vols) < self.median_window:
            return None

        median_vol = statistics.median(self.vols)
        threshold = median_vol * self.vol_multiple

        if not self._in_position and vol < threshold:
            self._in_position = True
            return "BUY"
        elif self._in_position and vol > threshold:
            self._in_position = False
            return "SELL"

        return None

    @property
    def is_ready(self) -> bool:
        return len(self.vols) >= self.median_window

