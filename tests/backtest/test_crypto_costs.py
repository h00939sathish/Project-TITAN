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
