"""Cost model attribution pieces."""

from decimal import Decimal

from titan.backtest.crypto_costs import CryptoCostModel


def test_taker_fee_and_spread_split():
    model = CryptoCostModel.binance_usdt_vip0()
    notional = Decimal("10000")
    fee = model.taker_fee(notional, perp=True)
    spread = model.spread_cost(notional)
    slip = model.slippage_cost(notional)
    assert fee == Decimal("5")  # 10k * 5 bps
    assert spread == Decimal("1")  # 1 bps
    assert slip == Decimal("0.5")
    assert fee != spread


def test_qty_precision_and_min_notional():
    model = CryptoCostModel.binance_usdt_vip0()
    assert model.round_qty(Decimal("1.123456789")) == Decimal("1.123457")
    assert model.min_notional == Decimal("5")


def test_adverse_fees_are_strictly_worse():
    model = CryptoCostModel.binance_usdt_vip0()
    n = Decimal("10000")
    assert model.taker_fee(n, perp=True, adverse=True) > model.taker_fee(n, perp=True)
    assert model.spread_cost(n, adverse=True) > model.spread_cost(n)


def test_binance_usdt_vip1_schedule():
    model = CryptoCostModel.binance_usdt_vip1()
    assert model.label == "binance_usdt_vip1_2026-08-14"
    assert model.spot_maker == Decimal("0.0002")  # 2 bps
    assert model.spot_taker == Decimal("0.0005")  # 5 bps
    assert model.perp_maker == Decimal("0.0001")  # 1 bps
    assert model.perp_taker == Decimal("0.0004")  # 4 bps
    assert model.slippage_bps == Decimal("0.5")
    assert model.assumed_spread_bps == Decimal("1.0")


def test_maker_fee_calculation():
    vip1 = CryptoCostModel.binance_usdt_vip1()
    notional = Decimal("10000")
    assert vip1.maker_fee(notional, perp=True) == Decimal("1.0")  # 10k * 1 bps = $1.00
    assert vip1.maker_fee(notional, perp=False) == Decimal("2.0")  # 10k * 2 bps = $2.00
    assert vip1.taker_fee(notional, perp=True) == Decimal("4.0")  # 10k * 4 bps = $4.00
    assert vip1.taker_fee(notional, perp=False) == Decimal("5.0")  # 10k * 5 bps = $5.00
