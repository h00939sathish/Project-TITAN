"""Spot metal definitions — XAUUSD (gold) only.

Quantity convention: 1 unit = 1 troy ounce.
step_size=1 means quantity must be a whole number of ounces.
"""

from titan._core import ContractType, Instrument, InstrumentId

SPOT_METALS: dict[str, dict] = {
    "XAUUSD": {
        "base": "XAU", "quote": "USD", "precision": 2,
        "tick_size": "0.01", "pip": "0.01",
    },
}

STEP_SIZE = 1
MULTIPLIER = "1.0"

SPOT_METAL_SYMBOLS = frozenset(SPOT_METALS.keys())


def spot_metal_instrument(symbol: str) -> Instrument | None:
    sym = symbol.upper()
    info = SPOT_METALS.get(sym)
    if info is None:
        return None
    return Instrument(
        InstrumentId(sym, "SPOT"),
        info["tick_size"],
        STEP_SIZE,
        MULTIPLIER,
        ContractType.Commodity,
        # ponytail: currency is quote (settlement currency), not base
        info["quote"],
        info["precision"],
    )
