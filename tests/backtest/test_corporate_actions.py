"""Tests for backtest fill model and corporate actions."""

from titan.backtest.corporate_actions import CorporateActionsDB, common_adjustments
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


class TestCorporateActions:
    def test_split_adjustment(self):
        db = CorporateActionsDB()
        db.register_split("2021-06-01", "AAPL", 4.0)
        bars = [
            {"date": "2021-05-01", "open": 200, "high": 210, "low": 195, "close": 205, "volume": 1000},
            {"date": "2021-06-15", "open": 50, "high": 52, "low": 49, "close": 51, "volume": 4000},
        ]
        adjusted = db.adjust_bars(bars)
        # Pre-split bar: prices / 4, volume * 4
        assert adjusted[0]["open"] == 50.0
        assert adjusted[0]["high"] == 52.5
        assert adjusted[0]["low"] == 48.75
        assert adjusted[0]["close"] == 51.25
        assert adjusted[0]["volume"] == 4000
        # Post-split bar: unchanged
        assert adjusted[1]["open"] == 50.0
        assert adjusted[1]["close"] == 51.0
        assert adjusted[1]["volume"] == 4000

    def test_dividend_adjustment(self):
        db = CorporateActionsDB()
        db.register_dividend("2022-03-15", "SPY", 1.50)
        bars = [
            {"date": "2022-03-01", "open": 450, "high": 455, "low": 448, "close": 452, "volume": 1000},
            {"date": "2022-03-20", "open": 460, "high": 462, "low": 458, "close": 461, "volume": 1000},
        ]
        adjusted = db.adjust_bars(bars)
        # Pre-dividend bar: all prices reduced by 1.50
        assert adjusted[0]["open"] == 448.50
        assert adjusted[0]["high"] == 453.50
        assert adjusted[0]["low"] == 446.50
        assert adjusted[0]["close"] == 450.50
        # Post-dividend bar: unchanged
        assert adjusted[1]["close"] == 461.0

    def test_split_volume_adjustment(self):
        db = CorporateActionsDB()
        db.register_split("2020-09-01", "SPY", 2.0)
        bars = [
            {"date": "2020-08-01", "open": 300, "high": 310, "low": 295, "close": 305, "volume": 5000},
            {"date": "2020-09-15", "open": 150, "high": 155, "low": 148, "close": 152, "volume": 10000},
        ]
        adjusted = db.adjust_bars(bars)
        # Pre-split volume * 2
        assert adjusted[0]["volume"] == 10000
        assert adjusted[0]["close"] == 152.50
        # Post-split unchanged
        assert adjusted[1]["volume"] == 10000

    def test_no_adjustment_without_events(self):
        db = CorporateActionsDB()
        bars = [
            {"date": "2023-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 500},
        ]
        adjusted = db.adjust_bars(bars)
        assert adjusted[0] == bars[0]

    def test_multiple_splits(self):
        db = CorporateActionsDB()
        db.register_split("2020-08-31", "AAPL", 4.0)
        db.register_split("2022-06-01", "AAPL", 2.0)
        bars = [
            {"date": "2020-01-15", "open": 320, "high": 325, "low": 315, "close": 322, "volume": 800},
            {"date": "2021-01-15", "open": 80, "high": 82, "low": 79, "close": 81, "volume": 3200},
            {"date": "2022-12-15", "open": 40, "high": 41, "low": 39, "close": 40.5, "volume": 6400},
        ]
        adjusted = db.adjust_bars(bars)
        # Earliest bar: divided by 4 then by 2 (= /8)
        assert adjusted[0]["open"] == 40.0
        assert adjusted[0]["close"] == 40.25
        assert adjusted[0]["volume"] == 6400
        # Middle bar: divided by 2 only
        assert adjusted[1]["open"] == 40.0
        assert adjusted[1]["close"] == 40.5
        assert adjusted[1]["volume"] == 6400
        # Latest bar: unchanged
        assert adjusted[2]["close"] == 40.5

    def test_common_adjustments_has_events(self):
        db = common_adjustments()
        assert len(db.dividends) > 0
        assert len(db.splits) == 0

    def test_adjust_preserves_field_count(self):
        db = CorporateActionsDB()
        db.register_split("2021-06-01", "AAPL", 4.0)
        db.register_dividend("2021-03-15", "SPY", 1.50)
        bar = {"date": "2021-01-01", "open": 200, "high": 210, "low": 195, "close": 205, "volume": 1000, "extra": True}
        adjusted = db.adjust_bars([bar])
        assert set(adjusted[0].keys()) == set(bar.keys())
