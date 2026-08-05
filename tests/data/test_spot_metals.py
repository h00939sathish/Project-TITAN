from titan._core import ContractType

from titan.data.spot_metals import spot_metal_instrument


def test_commodity_contract_type_is_exposed():
    assert str(ContractType.Commodity) == "Commodity"


def test_xauusd_instrument_uses_commodity_contract():
    instrument = spot_metal_instrument("xauusd")
    assert instrument is not None
    assert str(instrument.instrument_id) == "XAUUSD.SPOT"
    assert instrument.contract_type == ContractType.Commodity
    assert instrument.currency == "USD"
    assert instrument.step_size == 1


def test_xauusd_price_alignment():
    instrument = spot_metal_instrument("XAUUSD")
    assert instrument is not None
    assert instrument.is_price_aligned("2350.01")
    assert not instrument.is_price_aligned("2350.001")


def test_spot_metal_factory_rejects_unknown_symbol():
    assert spot_metal_instrument("XAGUSD") is None
