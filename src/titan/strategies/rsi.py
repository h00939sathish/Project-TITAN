"""Relative Strength Index strategy.

BUY when RSI crosses above oversold threshold,
SELL when RSI crosses below overbought threshold.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class RelativeStrengthIndex:
    """Relative Strength Index mean-reversion strategy.

    BUY when RSI transitions from <= oversold to > oversold.
    SELL when RSI transitions from >= overbought to < overbought.
    """

    window: int = 14
    oversold: float = 30.0
    overbought: float = 70.0

    prices: deque[float] = field(default_factory=deque)
    _state: str = "FLAT"
    _prev_rsi: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.window + 50:
            self.prices = deque(self.prices, maxlen=self.window + 50)

    def update(self, close_price: float) -> str | None:
        self.prices.append(close_price)
        if len(self.prices) < self.window + 1:
            return None

        window = list(self.prices)[-(self.window + 1):]
        gains = []
        losses = []
        for i in range(1, len(window)):
            delta = window[i] - window[i - 1]
            gains.append(max(delta, 0.0))
            losses.append(max(-delta, 0.0))

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        if avg_loss == 0.0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # BUY: RSI crosses UP from <= oversold to > oversold
        if self._state == "FLAT" and self._prev_rsi is not None and self._prev_rsi <= self.oversold < rsi:
            self._state = "LONG"
            self._prev_rsi = rsi
            return "BUY"
        # SELL: RSI crosses DOWN from >= overbought to < overbought
        if self._state == "LONG" and self._prev_rsi is not None and self._prev_rsi >= self.overbought > rsi:
            self._state = "FLAT"
            self._prev_rsi = rsi
            return "SELL"

        self._prev_rsi = rsi
        return None

    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.window + 1

