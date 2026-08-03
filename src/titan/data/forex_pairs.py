"""Forex pair definitions — naming convention: EURUSD, GBPUSD, etc.

Only USD-quote pairs are included (XXX/USD). Pairs where USD is the base
(USD/JPY, USD/CHF, USD/CAD) are excluded because the portfolio engine is
USD-only — their PnL is in JPY/CHF/CAD and needs FX conversion.
Add them when multi-currency portfolio valuation exists.

Quantity convention: 1 unit = 1000 base currency (micro lot).
- quantity=1000 → 1 micro lot (1000 EUR for EUR/USD)
- quantity=10000 → 1 mini lot
- quantity=100000 → 1 standard lot

Tick sizes follow standard forex pip conventions:
- 0.0001 for most XXX/USD pairs (1 pip)
"""

from titan._core import ContractType, Instrument, InstrumentId

FOREX_PAIRS: dict[str, dict] = {
    "EURUSD": {
        "base": "EUR", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "GBPUSD": {
        "base": "GBP", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "AUDUSD": {
        "base": "AUD", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "NZDUSD": {
        "base": "NZD", "quote": "USD", "precision": 5,
        "tick_size": "0.0001", "pip": "0.0001",
    },
    "XAUUSD": {
        "base": "XAU", "quote": "USD", "precision": 2,
        "tick_size": "0.01", "pip": "0.01", "step_size": 1,
    },
}

# 1 micro-lot = 1000 base currency units
STEP_SIZE = 1000
# ponytail: step_size=1000 (micro-lots). Per-mini-lot if intraday scalping matters.
# ponytail: no fractional lot sizes (0.5 micro-lot) — add when needed.
# ponytail: USD-quote pairs only. USDJPY/USDCHF/USDCAD excluded — add when multi-currency portfolio valuation exists.
MULTIPLIER = "1.0"

FOREX_SYMBOLS = frozenset(FOREX_PAIRS.keys())


def forex_instrument(symbol: str) -> Instrument | None:
    info = FOREX_PAIRS.get(symbol.upper())
    if info is None:
        return None
    return Instrument(
        InstrumentId(symbol, "FOREX"),
        info["tick_size"],
        info.get("step_size", STEP_SIZE),
        MULTIPLIER,
        ContractType.Forex,
        info["base"],
        info["precision"],
    )
