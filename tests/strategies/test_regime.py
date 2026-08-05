"""Tests for RegimeDetector + gate in StrategyBridge."""

import pytest

import titan.strategies.registrations  # noqa: F401
from titan.strategies.bridge import StrategyBridge
from titan.strategies.regime.atr import ATRRegimeDetector
from titan.strategies.regime.base import RegimeDetector, RegimeState


class TestATRRegimeDetector:
    def test_not_ready_with_few_prices(self):
        d = ATRRegimeDetector(vol_window=5, median_window=10)
        for p in [100.0] * 5:
            assert d.update(p) is None
        assert not d.is_ready

    def test_low_vol_regime(self):
        d = ATRRegimeDetector(vol_window=5, median_window=10, low_multiple=0.5)
        rng = _random_walk(100.0, 3.0, 60)
        low_vol = [100.0] * 60
        prices = rng + low_vol
        state = None
        for p in prices:
            state = d.update(p)
        assert state is not None, f"last state: {state}"
        assert state.regime == "LOW_VOL", f"got {state}"

    def test_high_vol_regime(self):
        d = ATRRegimeDetector(vol_window=5, median_window=10, high_multiple=0.5)
        low = [100.0 + (i % 2) * 0.1 for i in range(60)]
        rng = _random_walk(100.0, 3.0, 40)
        prices = low + rng
        state = None
        for p in prices:
            state = d.update(p)
        assert state is not None
        assert state.regime == "HIGH_VOL"

    def test_moderate_vol_regime(self):
        d = ATRRegimeDetector(
            vol_window=5, median_window=10, low_multiple=0.8, high_multiple=1.2
        )
        prices = [100.0 + (i % 3 - 1) * 0.5 for i in range(80)]
        state = None
        for p in prices:
            state = d.update(p)
        assert state is not None
        assert state.regime == "MODERATE_VOL"

    def test_regime_state_fields(self):
        d = ATRRegimeDetector(vol_window=5, median_window=10)
        prices = [100.0] * 25 + [100.0 + i * 3.0 for i in range(40)]
        state = None
        for p in prices:
            state = d.update(p)
        assert state is not None
        assert isinstance(state.regime, str)
        assert 0 <= state.confidence <= 1
        assert state.volatility in ("LOW", "MODERATE", "HIGH")
        assert 0 <= state.trend_strength <= 1


class TestStubRegimeDetector:
    """A deterministic stub detector for testing bridge gating."""

    @pytest.fixture
    def low_vol_detector(self):
        return _StubRegimeDetector(RegimeState(
            regime="LOW_VOL", confidence=0.8, volatility="LOW", trend_strength=0.2,
        ))

    @pytest.fixture
    def high_vol_detector(self):
        return _StubRegimeDetector(RegimeState(
            regime="HIGH_VOL", confidence=0.9, volatility="HIGH", trend_strength=0.6,
        ))

    def test_bridge_suppresses_on_high_vol(self, high_vol_detector):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            regime_detector=high_vol_detector,
        )
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 0

    def test_bridge_allows_on_low_vol(self, low_vol_detector):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            regime_detector=low_vol_detector,
        )
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 1
        assert intents[0].side == "BUY"

    def test_bridge_no_detector_still_works(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 1

    def test_warmup_feeds_detector(self, high_vol_detector):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            regime_detector=high_vol_detector,
        )
        bridge.warmup("SPY", [100] * 20)
        intent = bridge.on_price("SPY", 105)
        assert intent is None

    def test_custom_suppress_regimes(self):
        """Allow HIGH_VOL, suppress on everything else."""
        detector = _StubRegimeDetector(RegimeState(
            regime="LOW_VOL", confidence=0.7, volatility="LOW", trend_strength=0.1,
        ))
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            regime_detector=detector,
            suppress_regimes=("LOW_VOL", "MODERATE_VOL"),
        )
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 0


class _StubRegimeDetector(RegimeDetector):
    """Returns the same RegimeState on every call."""

    def __init__(self, state: RegimeState):
        self._state = state

    def update(self, price: float) -> RegimeState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return True


def _random_walk(start: float, step_sigma: float, n: int) -> list[float]:
    """Generate a random walk price series."""
    import random
    random.seed(42)
    prices = [start]
    for _ in range(n - 1):
        prices.append(prices[-1] + random.gauss(0, step_sigma))
    return [max(p, 1.0) for p in prices]
