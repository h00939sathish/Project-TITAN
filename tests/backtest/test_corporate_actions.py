"""Tests for backtest fill model."""

from titan.backtest.fills import BarConservativeFillModel, FillResult


class TestFillModel:
    def test_buy_fill(self):
        model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
        bar = {"open": 150, "high": 152, "low": 149, "close": 151.50}
        result = model.fill(bar, "buy", 100)
        assert result.fill_quantity == 100
        assert result.fill_price > bar["close"]  # slippage adds for buys
        assert result.commission > 0
        assert result.slippage > 0

    def test_sell_fill(self):
        model = BarConservativeFillModel()
        bar = {"open": 400, "high": 405, "low": 398, "close": 402}
        result = model.fill(bar, "sell", 50)
        assert result.fill_quantity == 50
        assert result.fill_price < bar["close"]  # slippage subtracts for sells

    def test_zero_commission_model(self):
        model = BarConservativeFillModel(slippage_bps=0, commission_bps=0)
        bar = {"close": 100}
        result = model.fill(bar, "buy", 10)
        assert result.fill_price == 100
        assert result.commission == 0
        assert result.slippage == 0

    def test_deterministic(self):
        """Same inputs → same outputs across runs."""
        model = BarConservativeFillModel()
        bar = {"close": 100.50}
        r1 = model.fill(bar, "buy", 100)
        r2 = model.fill(bar, "buy", 100)
        assert r1.fill_price == r2.fill_price
        assert r1.fill_cost == r2.fill_cost
