import json
from datetime import datetime, timezone

import pytest

import titan.strategies.registrations  # noqa: F401
from titan.runtime.events import MarketEvent, StrategyDefinition, TriggerSpec
from titan.strategies.multitimeframe_runtime import MultiTimeframeRuntime
from titan.strategies.registry import StrategyRegistration, get_registry
from titan.strategies.timeframes import Timeframe


@pytest.fixture(autouse=True)
def _add_test_timeframe_qualifications():
    """Give the strategies tests a qualified ma-crossover, then RESTORE the
    registry afterward. The registry is a process-global singleton: mutating it
    without restoration leaks baked variants into every later test session
    (observed: ADR-022 enforcement in tests/research/ failed only when the
    strategies suite ran first). Restore guarantees the baked variants never
    escape this fixture's test."""
    reg = get_registry()
    existing = reg._strategies["ma-crossover"]
    test_variants = set(existing.qualified_variants) | {
        (Timeframe.FIVE_MINUTES, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
        (Timeframe.FIFTEEN_MINUTES, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
        (Timeframe.ONE_HOUR, json.dumps({"fast": 5, "slow": 20}, sort_keys=True)),
        (Timeframe.FIVE_MINUTES, json.dumps({"fast": 2, "slow": 3}, sort_keys=True)),
        (Timeframe.FIFTEEN_MINUTES, json.dumps({"fast": 2, "slow": 3}, sort_keys=True)),
        (Timeframe.ONE_HOUR, json.dumps({"fast": 2, "slow": 3}, sort_keys=True)),
        (Timeframe.ONE_DAY, json.dumps({"fast": 2, "slow": 3}, sort_keys=True)),
    }
    reg._strategies["ma-crossover"] = StrategyRegistration(
        strategy_id=existing.strategy_id,
        version=existing.version,
        description=existing.description,
        parameter_schema=existing.parameter_schema,
        factory=existing.factory,
        qualified_variants=frozenset(test_variants),
    )
    yield
    # Restore the pristine registration (ADR-022: gate-only qualification).
    reg._strategies["ma-crossover"] = existing


@pytest.fixture
def t0():
    return datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def t1():
    return datetime(2026, 7, 24, 12, 5, 0, tzinfo=timezone.utc)


@pytest.fixture
def runtime():
    rt = MultiTimeframeRuntime()

    default_params = {"fast": 2, "slow": 3}
    for tf in (Timeframe.FIVE_MINUTES, Timeframe.FIFTEEN_MINUTES, Timeframe.ONE_HOUR, Timeframe.ONE_DAY):
        rt.register(StrategyDefinition(
            strategy_id="ma-crossover",
            trigger=TriggerSpec(event_type="BarClosed", timeframe=tf),
            params=default_params,
        ))
    return rt


@pytest.fixture
def event_factory():
    class _Factory:
        _counter = 0

        def bar_closed(self, instrument_id, timeframe, close, timestamp=None, received_at=None):
            self._counter += 1
            ts = timestamp or datetime.now(timezone.utc)
            ra = received_at or ts
            payload = {
                "timeframe": str(timeframe.value) if hasattr(timeframe, "value") else str(timeframe),
                "close": close,
            }
            return MarketEvent(
                message_id=f"evt-{self._counter}",
                causation_id="",
                correlation_id=f"corr-{self._counter}",
                occurred_at=ts,
                received_at=ra,
                schema_version=1,
                source="test",
                event_type="BarClosed",
                instrument_id=instrument_id,
                payload=payload,
                payload_digest="",
            )

    return _Factory()
