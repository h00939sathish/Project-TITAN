"""Tests for the TraderDev EMA9×VWAP trailing candidate strategy (EXP-00025)."""
import pytest
from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP
from titan.strategies.registry import get_registry
import titan.strategies.registrations  # noqa: F401 — triggers registration


class TestTraderDevEMA9VWAP:
    def test_not_ready_with_few_prices(self):
        strat = TraderDevEMA9VWAP(vwap_period=50, ema_period=9, atr_period=14)
        for p in [100 + i for i in range(10)]:
            strat.update(float(p))
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = TraderDevEMA9VWAP(vwap_period=20, ema_period=3, atr_period=5)
        for p in range(40):
            strat.update(float(100 + p))
        assert strat.is_ready

    def test_buy_on_uptrend_cross(self):
        # flat then sharp rise -> EMA9 crosses above the VWAP proxy -> BUY
        strat = TraderDevEMA9VWAP(vwap_period=20, ema_period=3, atr_period=5, trail_mult=3.0)
        signals = []
        for _ in range(25):
            s = strat.update(100.0)
            if s:
                signals.append(s)
        assert not signals  # flat: no cross
        for k in range(1, 40):
            s = strat.update(100.0 + k * 1.0)
            if s:
                signals.append(s)
                break
        assert "BUY" in signals
        assert strat._position == 1

    def test_trailing_stop_emits_sell(self):
        # flat then rise (establish long), then sharp drop trips the trail -> SELL
        strat = TraderDevEMA9VWAP(vwap_period=20, ema_period=3, atr_period=5, trail_mult=2.0)
        signals = []
        for _ in range(25):
            s = strat.update(100.0)
            if s:
                signals.append(s)
        for k in range(1, 20):
            s = strat.update(100.0 + k * 1.0)
            if s:
                signals.append(s)
                break
        assert "BUY" in signals
        base = list(strat.closes)[-1]
        for k in range(1, 40):
            s = strat.update(float(base - k * 3.0))
            if s:
                signals.append(s)
                break
        assert "SELL" in signals
        assert strat._position == 0

    def test_no_signal_in_flat_range(self):
        strat = TraderDevEMA9VWAP(vwap_period=20, ema_period=3, atr_period=5)
        signals = []
        for _ in range(60):
            s = strat.update(100.0)
            if s:
                signals.append(s)
        # flat line: no crossover, no trail trip -> no signal
        assert signals == []

    def test_callable_as_signal_fn(self):
        strat = TraderDevEMA9VWAP(vwap_period=20, ema_period=3, atr_period=5)
        out = strat({"close": 101.0})
        assert out is None or out in ("BUY", "SELL")


class TestTraderDevRegistration:
    def test_registered_not_qualified(self):
        reg = get_registry().get("traderdev-ema9-vwap")
        assert reg.strategy_id == "traderdev-ema9-vwap"
        # candidate: must NOT be auto-qualified for any timeframe
        assert len(reg.qualified_variants) == 0

    def test_factory_produces_signal_fn(self):
        from titan.strategies.registrations import make_traderdev_ema9vwap_signal_fn  # noqa
        fn = make_traderdev_ema9vwap_signal_fn({"ema_period": 9, "vwap_period": 240,
                                               "atr_period": 14, "trail_mult": 3.0})
        assert callable(fn)
        r = fn({"close": 1.1})
        assert r is None or r in ("BUY", "SELL")