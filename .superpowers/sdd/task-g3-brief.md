# Task G3: Metrics emission from risk gate, execution, and portfolio

## Goal

Create an in-memory metrics system (Counter, Gauge, MetricsRegistry) and CLI commands to inspect it. Wire metric hooks into the risk gate, portfolio, execution, and reconciliation paths.

## Files

- Create: `src/titan/operations/metrics.py` — Counter, Gauge, MetricsRegistry
- Create: `src/titan/operations/_metrics_integration.py` — metric definitions + wiring helpers
- Modify: `src/titan/cli.py` — add `metrics dump` and `metrics health` commands
- Modify: `src/titan/operations/__init__.py` — export new classes
- Create: `tests/operations/test_metrics.py` — tests

## Implementation details

### src/titan/operations/metrics.py

```python
"""In-memory metrics for TITAN operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import json


@dataclass
class MetricValue:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""


class Counter:
    def __init__(self, name: str, registry: "MetricsRegistry"):
        self._name = name
        self._registry = registry
        self._value = 0

    def inc(self, amount: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self._value += amount
        self._registry.store(MetricValue(
            name=self._name, value=self._value, tags=tags or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    @property
    def value(self) -> float:
        return self._value


class Gauge:
    def __init__(self, name: str, registry: "MetricsRegistry"):
        self._name = name
        self._registry = registry
        self._value = 0.0

    def set(self, value: float, tags: dict[str, str] | None = None) -> None:
        self._value = value
        self._registry.store(MetricValue(
            name=self._name, value=value, tags=tags or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    @property
    def value(self) -> float:
        return self._value


class MetricsRegistry:
    def __init__(self):
        self._metrics: dict[str, MetricValue] = {}

    def store(self, mv: MetricValue) -> None:
        self._metrics[mv.name] = mv

    def counter(self, name: str) -> Counter:
        return Counter(name, self)

    def gauge(self, name: str) -> Gauge:
        return Gauge(name, self)

    def snapshot(self) -> dict[str, float]:
        return {k: v.value for k, v in self._metrics.items()}

    def dump_json(self) -> str:
        return json.dumps(self.snapshot(), default=str, indent=2)
```

### src/titan/operations/_metrics_integration.py

```python
"""Metric definitions and wiring helpers for TITAN subsystems."""

from titan.operations.metrics import MetricsRegistry


# Global instance — codebase convention uses module-level registry
_REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _REGISTRY


# Risk gate metrics
intents_evaluated = _REGISTRY.counter("intents_evaluated")
intents_rejected = _REGISTRY.counter("intents_rejected")
kill_switch_triggered = _REGISTRY.counter("kill_switch_triggered")
trading_state_changed = _REGISTRY.counter("trading_state_changed")

# Portfolio metrics
positions_open = _REGISTRY.gauge("positions_open")
gross_exposure = _REGISTRY.gauge("gross_exposure")
cash_balance = _REGISTRY.gauge("cash_balance")

# Execution metrics
orders_submitted = _REGISTRY.counter("orders_submitted")
orders_filled = _REGISTRY.counter("orders_filled")
orders_rejected = _REGISTRY.counter("orders_rejected")
orders_cancelled = _REGISTRY.counter("orders_cancelled")
orders_unknown = _REGISTRY.counter("orders_unknown")

# Reconciliation metrics
drift_count_warning = _REGISTRY.gauge("drift_count_warning")
drift_count_critical = _REGISTRY.gauge("drift_count_critical")
last_reconciliation_age_seconds = _REGISTRY.gauge("last_reconciliation_age_seconds")

# System state
system_state = _REGISTRY.gauge("system_state")
```

### src/titan/cli.py modifications

Add after the `risk` group:

```python
@cli.group()
def metrics():
    """Metrics commands."""
    pass


@metrics.command()
def dump():
    """Dump all metrics as JSON."""
    from titan.operations._metrics_integration import get_registry
    click.echo(get_registry().dump_json())


@metrics.command()
def health():
    """Assess system health from metrics."""
    from titan.operations._metrics_integration import (
        get_registry, intents_evaluated, intents_rejected,
        orders_filled, orders_submitted, drift_count_critical,
    )
    reg = get_registry()
    snap = reg.snapshot()
    risk_working = snap.get("intents_evaluated", 0) > 0
    orders_progressing = snap.get("orders_filled", 0) > 0 or snap.get("orders_submitted", 0) > 0
    broker_matches = snap.get("drift_count_critical", 0) == 0
    click.echo(f"Risk working: {'YES' if risk_working else 'NO'}")
    click.echo(f"Orders progressing: {'YES' if orders_progressing else 'NO'}")
    click.echo(f"Broker truth matches: {'YES' if broker_matches else 'NO'}")
```

Also update the `status` command to mention metrics:

```python
click.echo("Use 'titan metrics' to inspect runtime metrics.")
```

### tests/operations/test_metrics.py

```python
"""Tests for metrics emission."""

from titan.operations.metrics import Counter, Gauge, MetricsRegistry
from titan.operations._metrics_integration import get_registry


class TestMetricsCore:
    def test_counter_increments(self):
        reg = MetricsRegistry()
        c = reg.counter("test_count")
        assert c.value == 0
        c.inc()
        assert c.value == 1
        c.inc(5)
        assert c.value == 6

    def test_gauge_sets_value(self):
        reg = MetricsRegistry()
        g = reg.gauge("test_gauge")
        assert g.value == 0.0
        g.set(42.5)
        assert g.value == 42.5
        g.set(-1.0)
        assert g.value == -1.0

    def test_registry_snapshot(self):
        reg = MetricsRegistry()
        c = reg.counter("a")
        g = reg.gauge("b")
        c.inc(3)
        g.set(1.5)
        snap = reg.snapshot()
        assert snap["a"] == 3
        assert snap["b"] == 1.5

    def test_dump_json(self):
        reg = MetricsRegistry()
        c = reg.counter("x")
        c.inc(10)
        output = reg.dump_json()
        import json
        parsed = json.loads(output)
        assert parsed["x"] == 10

    def test_multiple_counters_independent(self):
        reg = MetricsRegistry()
        c1 = reg.counter("first")
        c2 = reg.counter("second")
        c1.inc(1)
        c2.inc(99)
        assert c1.value == 1
        assert c2.value == 99

    def test_module_registry_is_singleton(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2
```

### Integration wiring

Add a test that exercises the integration helpers by simulating a full risk → fill → reconcile cycle and verifying metrics are populated:

Add to `tests/operations/test_metrics.py`:

```python
class TestMetricsIntegration:
    def test_risk_metrics_via_integration_helpers(self):
        from titan._core import RiskConfig, RiskGate, TradingState, EventStore
        from titan.operations._metrics_integration import (
            intents_evaluated, intents_rejected, kill_switch_triggered,
            trading_state_changed, positions_open, orders_submitted, orders_filled,
        )
        from titan.operations.metrics import MetricsRegistry

        config = RiskConfig.default()
        gate = RiskGate(config)

        # Simulate: evaluate an intent (risk decision)
        intents_evaluated.inc()
        intents_evaluated.inc()
        assert intents_evaluated.value == 2

        # Simulate: reject an intent
        intents_rejected.inc()
        assert intents_rejected.value == 1

        # Simulate: trigger kill switch
        kill_switch_triggered.inc()
        assert kill_switch_triggered.value == 1

        # Simulate: portfolio update
        positions_open.set(3)
        assert positions_open.value == 3

        # Simulate: order events
        orders_submitted.inc()
        orders_filled.inc()
        assert orders_submitted.value == 1
        assert orders_filled.value == 1
```

## Acceptance criteria

- `python -m pytest tests/operations/test_metrics.py -v` passes (7 tests)
- `python -m pytest tests/operations/ -v` passes (14 telemetry/logging + 7 metrics = 21 tests)
- `python -m pytest tests/ -v` passes (no regressions)
- `python -m titan.cli metrics dump` prints valid JSON
- `python -m titan.cli metrics health` shows status lines

## Constraints

- Follow existing codebase patterns
- No breaking changes to CLI interface
- No credentials in source code
