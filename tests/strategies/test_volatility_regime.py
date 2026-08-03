"""Tests for volatility-regime timing strategy."""

import math
from titan.strategies.volatility_regime import VolatilityRegime


class TestVolatilityRegime:
    def test_not_ready_with_few_prices(self):
        strat = VolatilityRegime(vol_window=5, median_window=10)
        for p in [100] * 8:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = VolatilityRegime(vol_window=5, median_window=10)
        # is_ready needs median_window (10) vol samples. Each vol requires a
        # return, and the first vol needs vol_window+1 = 6 closes; the remaining
        # 9 vol samples each need one more close => 15 closes minimum.
        for p in [100] * 15:
            strat.update(p)
        assert strat.is_ready

    def test_buy_in_low_vol_regime(self):
        strat = VolatilityRegime(vol_window=5, median_window=10, vol_multiple=1.0)
        prices = [100.0]
        for _ in range(20):
            prices.append(prices[-1] * 1.001)
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals

    def test_sell_in_high_vol_regime(self):
        strat = VolatilityRegime(vol_window=5, median_window=10, vol_multiple=1.0)
        prices = [100.0]
        # low-vol regime: steady drift up
        for _ in range(30):
            prices.append(prices[-1] * 1.001)
        # high-vol regime: large oscillations
        for _ in range(30):
            prices.append(prices[-1] * (1.0 + 0.025 if _ % 2 == 0 else 1.0 - 0.025))
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        has_sell = any(s == "SELL" for s in signals)
        assert has_sell

    def test_no_signal_constant_prices(self):
        strat = VolatilityRegime(vol_window=5, median_window=10, vol_multiple=1.0)
        for _ in range(100):
            sig = strat.update(100.0)
            assert sig is None

    def test_buy_then_sell_cycle(self):
        strat = VolatilityRegime(vol_window=5, median_window=10, vol_multiple=1.0)
        prices = [100.0]
        for _ in range(20):
            prices.append(prices[-1] * 1.001)
        for _ in range(10):
            prices.append(prices[-1] * (1.0 + 0.02 if _ % 2 == 0 else 1.0 - 0.02))
        signals = [s for p in prices if (s := strat.update(p))]
        assert "BUY" in signals
        assert "SELL" in signals
        assert signals.index("BUY") < signals.index("SELL")
