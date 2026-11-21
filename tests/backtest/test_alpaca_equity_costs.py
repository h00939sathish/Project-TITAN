"""Unit tests for the canonical Alpaca US Equity Cost Model."""

from decimal import Decimal
import pytest

from titan.backtest.alpaca_equity_costs import AlpacaEquityCostModel


def test_alpaca_zero_commission_on_buy():
    model = AlpacaEquityCostModel.standard_retail()

    # Buy 100 shares @ $150 = $15,000 notional
    breakdown = model.calculate_cost(side="buy", shares=100, price=150.0)

    # Commission must be exactly $0.00
    assert breakdown.commission_usd == Decimal("0.00")
    
    # Regulatory fees are $0.00 on BUY orders
    assert breakdown.sec_fee_usd == Decimal("0.00")
    assert breakdown.finra_taf_usd == Decimal("0.00")
    assert breakdown.borrow_fee_usd == Decimal("0.00")

    # Spread = $15,000 * 1.0 bps = $1.50
    assert breakdown.spread_usd == Decimal("1.5000")
    # Slippage = $15,000 * 0.5 bps = $0.75
    assert breakdown.slippage_usd == Decimal("0.7500")

    # Total friction = $1.50 + $0.75 = $2.25
    assert breakdown.total_friction_usd == Decimal("2.2500")


def test_alpaca_regulatory_fees_on_sell():
    model = AlpacaEquityCostModel.standard_retail()

    # Sell 1,000 shares @ $100 = $100,000 notional
    breakdown = model.calculate_cost(side="sell", shares=1000, price=100.0)

    # Commission = $0.00
    assert breakdown.commission_usd == Decimal("0.00")

    # SEC Fee: $100,000 * 0.0000278 = $2.78
    assert breakdown.sec_fee_usd == Decimal("2.78")

    # FINRA TAF: 1,000 shares * $0.000166 = $0.166 -> $0.17 rounded up
    assert breakdown.finra_taf_usd == Decimal("0.17")

    # Spread = $10.00, Slippage = $5.00
    assert breakdown.spread_usd == Decimal("10.0000")
    assert breakdown.slippage_usd == Decimal("5.0000")

    # Total = 10 + 5 + 2.78 + 0.17 = 17.95
    assert breakdown.total_friction_usd == Decimal("17.9500")


def test_alpaca_etb_short_zero_borrow():
    model = AlpacaEquityCostModel.standard_retail()

    # Short 500 shares @ $200 = $100,000 notional (ETB share held 10 days)
    breakdown = model.calculate_cost(
        side="sell_short",
        shares=500,
        price=200.0,
        is_etb=True,
        holding_days=10,
    )

    # Commission is $0.00
    assert breakdown.commission_usd == Decimal("0.00")

    # ETB borrow fee is strictly $0.00
    assert breakdown.borrow_fee_usd == Decimal("0.00")

    # Sells incur SEC & TAF
    assert breakdown.sec_fee_usd == Decimal("2.78")
    assert breakdown.finra_taf_usd == Decimal("0.09")


def test_alpaca_htb_short_penalty():
    model = AlpacaEquityCostModel.standard_retail()

    # Short 500 shares @ $200 = $100,000 notional (HTB share held 10 days)
    breakdown = model.calculate_cost(
        side="sell_short",
        shares=500,
        price=200.0,
        is_etb=False,
        holding_days=10,
    )

    # HTB incurs non-zero daily borrow fee
    assert breakdown.borrow_fee_usd > Decimal("0.00")
    # 100,000 * 0.0002 * 10 = $200.00
    assert breakdown.borrow_fee_usd == Decimal("200.00")


def test_alpaca_stressed_adverse_cost_schedule():
    model = AlpacaEquityCostModel.stressed_adverse()

    # Buy $10,000 notional under stress: 3.0 bps spread + 1.5 bps slippage
    breakdown = model.calculate_cost(side="buy", shares=100, price=100.0)

    assert breakdown.spread_usd == Decimal("3.0000")
    assert breakdown.slippage_usd == Decimal("1.5000")
    assert breakdown.total_friction_usd == Decimal("4.5000")


def test_alpaca_to_venue_cost_schedule():
    model = AlpacaEquityCostModel.standard_retail()
    schedule = model.to_venue_cost_schedule()

    assert schedule.name == "alpaca_retail_etb"
    assert schedule.commission_per_share_usd == 0.0
    assert schedule.min_commission_usd == 0.0
    assert schedule.annual_short_borrow_bps == 0.0
    assert schedule.spread_bps == 1.0
    assert schedule.slippage_bps == 0.5
    assert schedule.regulatory_fees_bps == 0.03
    assert schedule.assumption_status == "verified_from_published_schedule"
