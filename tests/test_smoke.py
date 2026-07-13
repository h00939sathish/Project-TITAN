"""Smoke tests for the TITAN platform bootstrap."""

from titan._core import InstrumentId, Money, Price, Quantity, Side, version


def test_version_returns_string() -> None:
    v = version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_money_construction() -> None:
    m = Money("100.50", "USD")
    assert m.amount == "100.50"
    assert m.currency == "USD"
    assert str(m) == "100.50 USD"


def test_quantity_construction() -> None:
    q = Quantity("1000")
    assert q.value == "1000"
    assert str(q) == "1000"


def test_price_construction() -> None:
    p = Price("150.25", 2)
    assert p.value == "150.25"
    assert p.precision == 2


def test_side_values() -> None:
    assert Side.Buy == Side.Buy
    assert Side.Sell == Side.Sell
    assert Side.Buy != Side.Sell


def test_instrument_id() -> None:
    inst = InstrumentId("AAPL", "NASDAQ")
    assert inst.symbol == "AAPL"
    assert inst.venue == "NASDAQ"
    assert str(inst) == "AAPL.NASDAQ"
