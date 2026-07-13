"""Tests for strategy manifest, runtime, and moving average strategy."""

import pytest
from titan.strategies.manifest import StrategyManifest
from titan.strategies.runtime import StrategyRuntime, StrategyRejection
from titan.strategies.moving_average import MovingAverageCrossover


class TestStrategyManifest:
    def test_manifest_creates_digest(self):
        m = StrategyManifest(
            package_id="ma-cross-v1",
            package_version="1.0.0",
            data_requirements=["ohlcv"],
            parameter_schema={"fast_period": 5, "slow_period": 20},
            universe=["AAPL", "MSFT"],
        )
        digest = m.compute_digest()
        assert len(digest) == 64
        m2 = StrategyManifest(
            package_id="ma-cross-v1",
            package_version="1.0.0",
            data_requirements=["ohlcv"],
            parameter_schema={"fast_period": 5, "slow_period": 20},
            universe=["AAPL", "MSFT"],
        )
        assert m.compute_digest() == m2.compute_digest()

    def test_manifest_verify(self):
        m = StrategyManifest(
            package_id="test", package_version="1",
            package_digest="", universe=["AAPL"],
        )
        assert not m.verify()
        d = m.compute_digest()
        m2 = StrategyManifest(
            package_id="test", package_version="1",
            package_digest=d, universe=["AAPL"],
        )
        assert m2.verify()

    def test_different_params_different_digest(self):
        m1 = StrategyManifest("id", "1", universe=["AAPL"])
        m2 = StrategyManifest("id", "1", universe=["MSFT"])
        assert m1.compute_digest() != m2.compute_digest()


class TestMovingAverageCrossover:
    def test_not_ready_with_few_prices(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=5)
        for p in [100, 101, 102]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_signal_on_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        # Dip then rise — fast crosses above slow
        prices = [100, 90, 80, 85, 90, 95]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals

    def test_sell_signal_on_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        # Rise then fall — fast crosses below slow
        prices = [100, 90, 100, 110, 100, 90]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "SELL" in signals

    def test_no_signal_without_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        for p in [100, 100, 100, 100, 100, 100]:
            sig = strat.update(p)
            assert sig is None


class TestStrategyRuntime:
    def test_register_and_emit(self):
        m = StrategyManifest("ma-cross", "1.0", universe=["AAPL", "MSFT"])
        manifest = StrategyManifest(
            "ma-cross", "1.0",
            package_digest=m.compute_digest(),
            universe=["AAPL", "MSFT"],
        )
        rt = StrategyRuntime()
        strat = MovingAverageCrossover()
        rt.register("ma-cross", strat, manifest)
        intent = rt.emit_intent("ma-cross", "AAPL", "BUY", "100", price="150")
        assert intent.strategy_id == "ma-cross"
        assert intent.instrument_id == "AAPL"
        assert intent.strategy_package_digest == manifest.package_digest

    def test_reject_unknown_instrument(self):
        manifest = StrategyManifest(
            "ma-cross", "1.0",
            package_digest=StrategyManifest("ma-cross", "1.0", universe=["AAPL"]).compute_digest(),
            universe=["AAPL"],
        )
        rt = StrategyRuntime()
        rt.register("ma-cross", object(), manifest)
        with pytest.raises(StrategyRejection, match="not in strategy universe"):
            rt.emit_intent("ma-cross", "GOOGL", "BUY", "100")

    def test_reject_unknown_strategy(self):
        rt = StrategyRuntime()
        with pytest.raises(StrategyRejection, match="Unknown strategy"):
            rt.emit_intent("unknown", "AAPL", "BUY", "100")

    def test_reject_bad_digest(self):
        manifest = StrategyManifest("x", "1", package_digest="bad"*16, universe=["AAPL"])
        rt = StrategyRuntime()
        with pytest.raises(ValueError, match="digest mismatch"):
            rt.register("x", object(), manifest)
