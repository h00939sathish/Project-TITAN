"""Tests for Bollinger Bands strategy."""

import pytest
from titan.strategies.bollinger import BollingerBands


class TestBollingerBands:
    def test_not_ready_with_few_prices(self):
        strat = BollingerBands(window=5)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = BollingerBands(window=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_when_price_hits_lower_band(self):
        strat = BollingerBands(window=5, std_dev_multiplier=2.0)
        prices = [100, 100, 100, 100, 100, 85, 80]
        signals = []
        for price in prices:
            signal = strat.update(price)
            if signal:
                signals.append(signal)
        assert "BUY" in signals
        assert strat._in_position is True

    def test_sell_when_price_reverts_to_middle(self):
        strat = BollingerBands(window=5, std_dev_multiplier=2.0)
        prices = [100, 100, 100, 100, 100, 85, 80, 90, 100, 100]
        signals = []
        for price in prices:
            signal = strat.update(price)
            if signal:
                signals.append(signal)
        assert "BUY" in signals
        assert "SELL" in signals
        assert signals.index("BUY") < signals.index("SELL")

    def test_no_signal_in_normal_range(self):
        strat = BollingerBands(window=5, std_dev_multiplier=2.0)
        prices = [100, 101, 99, 100, 102, 101, 100]
        signals = []
        for price in prices:
            signal = strat.update(price)
            if signal:
                signals.append(signal)
        assert signals == []

    def test_no_double_buy(self):
        strat = BollingerBands(window=5, std_dev_multiplier=2.0)
        prices = [100, 100, 100, 100, 100, 80, 75, 70]
        signals = [s for p in prices if (s := strat.update(p))]
        assert signals.count("BUY") <= 1
