"""Tests for time-series momentum strategy."""

from titan.strategies.momentum import TimeSeriesMomentum


class TestTimeSeriesMomentum:
    def test_not_ready_with_few_prices(self):
        strat = TimeSeriesMomentum(lookback=5)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = TimeSeriesMomentum(lookback=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_signal_on_positive_return(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 110]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals
        assert strat._position == "LONG"

    def test_sell_signal_on_negative_return(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 90]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "SELL" in signals
        assert strat._position == "SHORT"

    def test_no_signal_before_ready(self):
        strat = TimeSeriesMomentum(lookback=5)
        for p in [100, 101, 102, 103]:
            sig = strat.update(p)
            assert sig is None

    def test_transition_long_to_short(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 110, 90]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert signals == ["BUY", "SELL"]
        assert strat._position == "FLAT"

    def test_transition_short_to_long(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 90, 110]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert signals == ["SELL", "BUY"]
        assert strat._position == "FLAT"

    def test_no_duplicate_signals(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 110, 112, 115]
        signals = [s for p in prices if (s := strat.update(p))]
        assert signals == ["BUY"]

    def test_no_signal_on_zero_return(self):
        strat = TimeSeriesMomentum(lookback=3)
        prices = [100, 100, 100, 100, 100]
        for p in prices:
            sig = strat.update(p)
            assert sig is None

    def test_is_ready_property(self):
        strat = TimeSeriesMomentum(lookback=10)
        assert not strat.is_ready
        for i in range(10):
            strat.update(100.0)
            assert not strat.is_ready
        strat.update(100.0)
        assert strat.is_ready
