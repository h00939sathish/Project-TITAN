"""Tests for mean-reversion strategy."""

from titan.strategies.mean_reversion import MeanReversion


class TestMeanReversion:
    def test_not_ready_with_few_prices(self):
        strat = MeanReversion(window=5)
        for p in [100, 101, 102]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = MeanReversion(window=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_signal_on_oversold(self):
        strat = MeanReversion(window=5, entry_z=-1.5, exit_z=-0.3)
        # Steady then sharp drop — z-score goes below entry_z
        prices = [100, 100, 100, 100, 100, 80, 80]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals

    def test_sell_signal_on_reversion(self):
        strat = MeanReversion(window=5, entry_z=-1.5, exit_z=-0.3)
        # Drop into oversold (BUY), then recover toward mean (SELL)
        prices = [100, 100, 100, 100, 100, 80, 80, 90, 95, 98]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals
        assert "SELL" in signals
        # BUY must come before SELL
        assert signals.index("BUY") < signals.index("SELL")

    def test_no_signal_in_normal_market(self):
        strat = MeanReversion(window=5, entry_z=-2.0)
        for p in [100, 101, 99, 100, 102, 101, 100]:
            sig = strat.update(p)
            assert sig is None

    def test_no_double_buy(self):
        strat = MeanReversion(window=5, entry_z=-1.5, exit_z=-0.3)
        prices = [100, 100, 100, 100, 100, 80, 80]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert signals.count("BUY") <= 1

    def test_buy_requires_oversold_condition(self):
        strat = MeanReversion(window=5, entry_z=-2.0)
        # Small fluctuation should not trigger
        prices = [100, 101, 99, 100, 102, 98, 100]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" not in signals
