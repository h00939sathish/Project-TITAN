"""Tests for Relative Strength Index strategy."""

import pytest
from titan.strategies.rsi import RelativeStrengthIndex


class TestRelativeStrengthIndex:
    def test_not_ready_with_few_prices(self):
        strat = RelativeStrengthIndex(window=5)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = RelativeStrengthIndex(window=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_when_rsi_recovers_from_oversold(self):
        strat = RelativeStrengthIndex(window=5, oversold=30.0, overbought=70.0)
        # Steady prices then sharp drop -> oversold, then recovery
        prices = [100, 100, 100, 100, 100, 85, 80, 82, 85, 90, 95]
        signals = []
        for price in prices:
            signal = strat.update(price)
            if signal:
                signals.append(signal)
        assert "BUY" in signals
        assert strat._state == "LONG"

    def test_sell_when_rsi_falls_from_overbought(self):
        strat = RelativeStrengthIndex(window=5, oversold=30.0, overbought=70.0)
        # Drop -> BUY, rise -> overbought, then sharp decline -> SELL
        prices = [100, 98, 95, 92, 90, 88, 86, 85, 86, 90, 95, 100, 105, 110, 115, 120, 115, 108, 100, 95, 90]
        signals = []
        for price in prices:
            signal = strat.update(price)
            if signal:
                signals.append(signal)
        assert "BUY" in signals
        assert "SELL" in signals
        assert signals.index("BUY") < signals.index("SELL")

    def test_no_signal_before_ready(self):
        strat = RelativeStrengthIndex(window=5)
        for p in [100, 101, 102, 103]:
            signal = strat.update(p)
            assert signal is None

    def test_no_duplicate_signals(self):
        strat = RelativeStrengthIndex(window=3, oversold=30.0, overbought=70.0)
        prices = [100, 99, 98, 99, 100, 101, 102]
        signals = [s for p in prices if (s := strat.update(p))]
        assert signals.count("BUY") <= 1
