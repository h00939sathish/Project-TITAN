# tests/data/test_forex_pairs.py
from titan._core import ContractType

from titan.data.forex_pairs import FOREX_PAIRS, FOREX_SYMBOLS, forex_instrument


def test_forex_symbols_defined():
    # 4 currency pairs + XAUUSD (gold, step_size 1 oz) added for TWS IDEALPRO.
    assert len(FOREX_PAIRS) == 5
    assert "EURUSD" in FOREX_SYMBOLS
    assert "XAUUSD" in FOREX_SYMBOLS


def test_xauusd_instrument_creation():
    inst = forex_instrument("XAUUSD")
    assert inst is not None
    assert inst.contract_type == ContractType.Forex
    assert inst.currency == "XAU"
    assert inst.step_size == 1  # gold is 1 oz, not a 1000-unit micro-lot


def test_forex_instrument_creation():
    inst = forex_instrument("EURUSD")
    assert inst is not None
    assert inst.contract_type == ContractType.Forex
    assert inst.currency == "EUR"
    assert inst.step_size == 1000


def test_forex_instrument_unknown():
    assert forex_instrument("ZZZZZZ") is None


def test_forex_notional():
    inst = forex_instrument("EURUSD")
    # 1 micro-lot (1000) at 1.1000 = 1100 USD
    notional = inst.compute_notional(1000, "1.1000")
    assert notional == "1100.00000"
