"""Unit tests for FxCostModel fee calculations, serialization, and digests."""

from decimal import Decimal
import pytest

from titan.backtest.fx_costs import FxCostModel


def test_tier_one_ibkr_minimum_applies_to_a_10k_usd_fill():
    model = FxCostModel.ibkr_spot_fx_tier_one()
    # 10,000 * 0.2 bps / 10,000 = 0.20 USD -> clamped to minimum 2.00 USD
    assert model.commission_for_fill(Decimal("10000")) == Decimal("2.00")


def test_fee_rate_applies_above_the_minimum():
    model = FxCostModel.ibkr_spot_fx_tier_one()
    # 200,000 * 0.2 bps / 10,000 = 4.00 USD > 2.00 USD
    assert model.commission_for_fill(Decimal("200000")) == Decimal("4.00")


def test_cost_model_digest_changes_when_a_cost_changes():
    baseline = FxCostModel.ibkr_spot_fx_tier_one()
    stressed = baseline.with_adverse_costs()
    assert baseline.digest() != stressed.digest()


def test_cost_model_deterministic_digest():
    m1 = FxCostModel.ibkr_spot_fx_tier_one()
    m2 = FxCostModel.ibkr_spot_fx_tier_one()
    assert m1.digest() == m2.digest()


def test_cost_model_accepts_non_usd_v2():
    model = FxCostModel(
        venue="IDEALPRO",
        account_currency="USD",
        quote_currency="EUR",
        commission_bps=Decimal("0.2"),
        minimum_commission=Decimal("2.00"),
        half_spread_bps=Decimal("0.1"),
        slippage_bps=Decimal("0.2"),
        fill_mode="QUOTE_NEXT_EVENT",
    )
    assert model.quote_currency == "EUR"





def test_buy_quote_fill_uses_ask_and_charges_commission():
    from titan.backtest.fills import BarConservativeFillModel

    model = BarConservativeFillModel()
    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
    fill = model.fill(
        {"ask": Decimal("1.1002"), "bid": Decimal("1.1000")},
        "buy",
        Decimal("10000"),
        cost_model=cost_model,
    )
    # ask 1.1002 + slippage (0.10 bps = 0.000011002) = 1.100211002
    assert fill.fill_price >= Decimal("1.1002")
    assert fill.commission == Decimal("2.00")
    assert fill.fidelity in ("quote", "standard")


def test_bar_fill_requires_next_open_and_is_lower_fidelity():
    from titan.backtest.fills import BarConservativeFillModel

    model = BarConservativeFillModel()
    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="BAR_NEXT_OPEN")
    fill = model.fill(
        {"open": Decimal("1.1000")},
        "sell",
        Decimal("10000"),
        cost_model=cost_model,
    )
    assert fill.fidelity == "lower"
    assert fill.commission == Decimal("2.00")


def test_missing_required_quote_rejects_quote_fill():
    from titan.backtest.fills import BarConservativeFillModel

    model = BarConservativeFillModel()
    cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
    with pytest.raises(ValueError, match="ask"):
        model.fill(
            {"bid": Decimal("1.1000")},
            "buy",
            Decimal("10000"),
            cost_model=cost_model,
        )


def test_wednesday_triple_swap():
    model = FxCostModel.ibkr_spot_fx_tier_one()
    # 0 = Mon, 1 = Tue, 2 = Wed, 3 = Thu, 4 = Fri, 5 = Sat, 6 = Sun
    assert model.daily_swap_multiplier(0) == 1
    assert model.daily_swap_multiplier(2) == 3
    assert model.daily_swap_multiplier(5) == 0
