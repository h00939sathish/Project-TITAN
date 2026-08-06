"""Central Bank Policy & OIS Interest Rate Differential Ingestion Module.

Fulfills RQ-FX-001 / FX-CARRY-VOL strategy specifications from FOREX_STRATEGIES.md.
Maintains interest rate differentials across G10 and major currencies to evaluate
carry yield differentials and volatility-scaled carry scores.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Standard G10 Central Bank Policy / OIS Benchmark Rates (in % per annum)
DEFAULT_CENTRAL_BANK_RATES: dict[str, float] = {
    "USD": 5.25,  # US Federal Reserve (FFR target upper bound)
    "EUR": 3.75,  # European Central Bank (Deposit facility rate)
    "GBP": 5.00,  # Bank of England (Bank Rate)
    "JPY": 0.25,  # Bank of Japan (Policy rate)
    "CHF": 1.25,  # Swiss National Bank (Policy rate)
    "AUD": 4.35,  # Reserve Bank of Australia (Cash rate)
    "NZD": 5.25,  # Reserve Bank of New Zealand (Official cash rate)
    "CAD": 4.50,  # Bank of Canada (Overnight rate)
    "XAU": 0.00,  # Spot Gold (zero explicit yield baseline)
}

# Currency Pair Base/Quote Mapping
PAIR_CURRENCIES: dict[str, tuple[str, str]] = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USDCHF": ("USD", "CHF"),
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "EURGBP": ("EUR", "GBP"),
    "EURJPY": ("EUR", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
    "XAUUSD": ("XAU", "USD"),
}


@dataclass
class CentralBankRateStore:
    """Stores central bank benchmark interest rates and computes pair differentials."""

    rates: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CENTRAL_BANK_RATES))
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update_rate(self, currency: str, rate_pct: float) -> None:
        """Update policy rate for a specific currency."""
        self.rates[currency.upper()] = float(rate_pct)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_rate(self, currency: str) -> float:
        """Get current policy rate for currency, defaulting to 0.0% if unknown."""
        return self.rates.get(currency.upper(), 0.0)

    def get_pair_rate_differential(self, symbol: str) -> float:
        """Compute interest rate differential in basis points per annum.

        For pair BASE/QUOTE (e.g. EUR/USD):
            RateDiff = (r_base - r_quote) * 100 bps
        A positive differential means holding long position earns net yield;
        a negative differential means holding long position pays net yield.
        """
        sym = symbol.upper().replace("/", "")
        if sym not in PAIR_CURRENCIES:
            base, quote = sym[:3], sym[3:] if len(sym) >= 6 else "USD"
        else:
            base, quote = PAIR_CURRENCIES[sym]

        r_base = self.get_rate(base)
        r_quote = self.get_rate(quote)

        # Differential in annualized basis points (r_base - r_quote) * 100
        diff_pct = r_base - r_quote
        return round(diff_pct * 100.0, 2)  # in basis points


# Global default rate store instance
_DEFAULT_STORE = CentralBankRateStore()


def get_rate_differential(symbol: str, store: CentralBankRateStore | None = None) -> float:
    """Return annualized interest rate differential in basis points for a pair."""
    s = store or _DEFAULT_STORE
    return s.get_pair_rate_differential(symbol)


def compute_volatility_weighted_carry_score(
    symbol: str,
    prices: list[float],
    store: CentralBankRateStore | None = None,
    vol_window: int = 30,
) -> float:
    """Compute volatility-scaled carry score for a given price series.

    Formula:
        CarryScore = RateDiffBps / (AnnualizedVolPct * 100)
    """
    if not prices or len(prices) < 2:
        return 0.0

    diff_bps = get_rate_differential(symbol, store)
    if diff_bps == 0.0:
        return 0.0

    window_prices = prices[-vol_window:] if len(prices) > vol_window else prices
    returns = [
        math.log(window_prices[i] / window_prices[i - 1])
        for i in range(1, len(window_prices))
        if window_prices[i - 1] > 0
    ]

    if not returns or len(returns) < 2:
        return 0.0

    stdev_r = statistics.stdev(returns)
    annual_vol_pct = stdev_r * (252.0 ** 0.5) * 100.0

    if annual_vol_pct <= 1e-4:
        return round(diff_bps / 1.0, 4)

    score = diff_bps / annual_vol_pct
    return round(score, 4)
