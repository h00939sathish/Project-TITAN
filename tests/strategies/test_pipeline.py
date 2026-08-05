"""Tests for PipelineOrchestrator — the integration layer."""

from titan.strategies.pipeline import PipelineOrchestrator, StrategySlot, PipelineResult
from titan.strategies.regime.base import RegimeDetector, RegimeState
from titan.strategies.filters import SignalFilter, WeeklyTrendFilter
from titan.strategies.lifecycle import LifecycleEngine
from titan.strategies.allocator import MetaAllocator
from titan.strategies.shadow import ShadowDeployer
from titan.strategies.ensemble import WeightedEnsemble, StrategyVote


class DummyRegime(RegimeDetector):
    def __init__(self, regime="NORMAL", confidence=0.8, volatility="0.2"):
        self._regime = regime
        self._confidence = confidence
        self._volatility = volatility
        self._trend = 0.5
    def update(self, price: float) -> RegimeState | None:
        return RegimeState(self._regime, self._confidence, self._volatility, self._trend)
    def reset(self): pass
    def is_ready(self) -> bool:
        return True
    @property
    def state(self) -> RegimeState | None:
        return RegimeState(self._regime, self._confidence, self._volatility, self._trend)


class PassFilter(SignalFilter):
    def check(self, price: float, htf_prices: list[float] | None = None) -> bool:
        return True


class BlockFilter(SignalFilter):
    def check(self, price: float, htf_prices: list[float] | None = None) -> bool:
        return False


def test_pipeline_returns_result():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
        regime_detector=DummyRegime(),
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    assert isinstance(result, PipelineResult)
    assert result.regime is not None
    assert result.regime.regime == "NORMAL"


def test_regime_scales_position_size():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
        regime_detector=DummyRegime(regime="HIGH_VOL"),
        regime_size_multipliers={"HIGH_VOL": 0.25},
        order_size=100,
    )

    pipe.set_position("AAPL", False)
    # Flat prices then uptick → MA crossover BUY signal
    pipe.warmup("AAPL", [100.0] * 25, [100.0] * 25)
    result = pipe.run("AAPL", 101.0, "2026-07-23")
    assert result.intent is not None, f"intent was None: suppressed_by={result.suppressed_by}, ensemble={result.ensemble}"
    qty = int(result.intent.quantity)
    assert qty <= 25  # 100 * 0.25 = 25 max


def test_filter_suppresses_trades():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
        filters=[BlockFilter()],
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    assert result.suppressed_by == "filter"
    assert result.intent is None


def test_pass_filter_allows_trades():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
        filters=[PassFilter()],
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    assert result.ensemble is not None


def test_manifest_is_produced():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    assert result.manifest is not None
    assert result.manifest.instrument_id == "AAPL"


def test_lifecycle_tracks_strategies():
    lc = LifecycleEngine()
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20}), StrategySlot("rsi", {"period": 14})],
        lifecycle=lc,
    )
    assert "ma-crossover" in lc._strategies
    assert "rsi" in lc._strategies


def test_allocator_tracks_strategies():
    alloc = MetaAllocator()
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20}), StrategySlot("rsi", {"period": 14})],
        allocator=alloc,
    )
    assert "ma-crossover" in alloc._records
    assert "rsi" in alloc._records


def test_last_result_property():
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
    )
    assert pipe.last_result is None
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    pipe.run("AAPL", 105.0, "2026-07-23")
    assert pipe.last_result is not None


def test_shadow_records_if_provided():
    shadow = ShadowDeployer()
    pipe = PipelineOrchestrator(
        strategies=[StrategySlot("ma-crossover", {"fast": 5, "slow": 20})],
        shadow=shadow,
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    if result.intent:
        assert len(shadow._trades) > 0


def test_multiple_strategies_ensemble_voting():
    pipe = PipelineOrchestrator(
        strategies=[
            StrategySlot("ma-crossover", {"fast": 5, "slow": 20}),
            StrategySlot("ma-crossover", {"fast": 10, "slow": 30}),
        ],
    )
    pipe.set_position("AAPL", False)
    pipe.warmup("AAPL", [100, 101, 102, 103, 104])
    result = pipe.run("AAPL", 105.0, "2026-07-23")
    assert result.ensemble is not None
