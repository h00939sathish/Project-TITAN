"""Volatility-Weighted Currency Carry Strategy (FX-CARRY-VOL).

Fulfills RQ-FX-001 strategy specification from FOREX_STRATEGIES.md.
Generates BUY/SELL signals based on volatility-scaled interest rate differentials
and realized price volatility across currency pairs.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from titan.data.rate_differentials import (
    CentralBankRateStore,
    compute_volatility_weighted_carry_score,
    get_rate_differential,
)


@dataclass
class VolatilityWeightedCarry:
    """Volatility-weighted currency carry strategy (FX-CARRY-VOL).

    Generates BUY when base interest rate > quote interest rate with positive
    volatility-scaled yield, and SELL when quote interest rate > base interest rate.
    """

    symbol: str = "EURUSD"
    min_diff_bps: float = 10.0  # Minimum 10 bps rate differential threshold
    vol_window: int = 30
    rate_store: CentralBankRateStore = field(default_factory=CentralBankRateStore)
    prices: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if not isinstance(self.prices, deque) or self.prices.maxlen != self.vol_window + 50:
            self.prices = deque(self.prices, maxlen=self.vol_window + 50)

    def update(self, close_price: float) -> str | None:
        """Update strategy with new price and return BUY/SELL signal or None."""
        self.prices.append(close_price)

        diff_bps = get_rate_differential(self.symbol, self.rate_store)
        if abs(diff_bps) < self.min_diff_bps:
            return None

        # Compute volatility-scaled score if enough price history
        if len(self.prices) >= 5:
            score = compute_volatility_weighted_carry_score(
                self.symbol, list(self.prices), store=self.rate_store, vol_window=self.vol_window
            )
            if score >= 1.0:
                return "BUY"
            elif score <= -1.0:
                return "SELL"

        # Signal based directly on rate differential direction if prices are building
        if diff_bps > 0:
            return "BUY"
        elif diff_bps < 0:
            return "SELL"

        return None
