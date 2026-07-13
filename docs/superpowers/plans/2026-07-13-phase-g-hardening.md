# Phase G — Cross-Cutting Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Close the highest-priority gaps identified in the Phase F ORR — state persistence, structured logging, metrics emission, FAILURE_MATRIX test coverage, recovery automation, and performance benchmarking.

**Architecture:** Rust (via PyO3) owns state persistence (RiskStateSnapshot events, event store recovery); Python owns logging, metrics, CLI commands, test harnesses, and benchmark scripts.

**Tech Stack:** Python 3.14, Rust edition 2024, PyO3 0.29, rusqlite 0.34 (bundled), pytest, JSON logging (stdlib).

## Global Constraints

- Kill-switch state defaults to HALTED on unreadable state (fail-closed).
- No credentials in source, logs, or metrics.
- Structured logs carry correlation_id and causation_id on every event.
- Metrics are in-memory for paper phase (no external metrics backend required).
- FAILURE_MATRIX tests verify expected failure behavior AND recovery path.
- Benchmarks are reproducible: fixed seed, fixed dataset, recorded artifact digest.
- All existing tests continue to pass (118 Python + 62 Rust).
- No code is copied without license review per ADR-0002.

---

### Task G1: Kill-switch and trading-state persistence

**Files:**
- Modify: `core/src/risk.rs` — add `persist_state()` and `restore_state()` methods
- Modify: `core/src/messages.rs` — add `RiskStateSnapshot` event
- Modify: `core/src/event_store.rs` — ensure snapshots are appendable/replayable
- Create: `tests/risk/test_state_persistence.py`

**What to build:**

1. **`core/src/messages.rs`** — Add `RiskStateSnapshot` event variant:
```rust
/// Event emitted when risk gate state is persisted.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RiskStateSnapshot {
    pub message_id: Uuid,
    pub occurred_at: DateTime<Utc>,
    pub kill_switch_state: String,        // "Armed" | "Triggered" | "Releasing" | "Released"
    pub trading_state: String,            // "Active" | "Reducing" | "Halted"
    pub correlation_id: String,
    pub causation_id: String,
}
```

2. **`core/src/risk.rs`** — Add to `RiskGate`:
```rust
pub fn persist_state(&self, store: &mut EventStore) -> Result<(), EventStoreError> {
    let snapshot = RiskStateSnapshot {
        message_id: Uuid::new_v4(),
        occurred_at: Utc::now(),
        kill_switch_state: format!("{}", self.kill_switch.current_state()),
        trading_state: format!("{}", self.trading_state.current_state()),
        correlation_id: "system".to_string(),
        causation_id: "system".to_string(),
    };
    store.append(EventEnvelope { /* ... */ })?;
    Ok(())
}

pub fn restore_state(&mut self, store: &EventStore) -> Result<(), EventStoreError> {
    let events = store.replay_by_type("RiskStateSnapshot")?;
    if let Some(latest) = events.last() {
        // Parse and apply saved state
        // Default to HALTED if unreadable
    }
    Ok(())
}
```

3. **`tests/risk/test_state_persistence.py`** — Integration tests:
- Trigger kill switch → `persist_state()` → create new RiskGate → `restore_state()` → verify kill switch still triggered
- Create RiskGate with no persisted state → verify defaults to HALTED
- Persist trading state HALTED → restore → verify intents rejected

**Exit criteria:** `python -m pytest tests/risk/test_state_persistence.py -v` passes. Kill switch and trading state survive process restart.

---

### Task G2: Structured logging wired into runtime

**Files:**
- Modify: `src/titan/operations/telemetry.py` — keep existing classes, no breaking changes
- Create: `src/titan/operations/logging.py` — LogEvent, StructuredLogger
- Modify: `src/titan/cli.py` — wire structured logging to risk/adapter/reconciliation paths
- Create: `tests/operations/test_logging.py`

**What to build:**

1. **`src/titan/operations/logging.py`**:
```python
"""Structured JSON logging for TITAN operations."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
import sys


class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEvent:
    timestamp: str = ""
    severity: LogSeverity = LogSeverity.INFO
    component: str = ""
    message: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d["timestamp"] = self.timestamp or datetime.now(timezone.utc).isoformat()
        return json.dumps(d, default=str)


class StructuredLogger:
    def __init__(self, min_severity: LogSeverity = LogSeverity.INFO, output=None):
        self._min = min_severity
        self._output = output or sys.stdout

    def _log(self, severity: LogSeverity, component: str, message: str,
             correlation_id: str = "", causation_id: str = "",
             payload: dict | None = None) -> None:
        if severity.value < self._min.value:
            return
        event = LogEvent(
            severity=severity, component=component, message=message,
            correlation_id=correlation_id, causation_id=causation_id,
            payload=payload or {},
        )
        print(event.to_json(), file=self._output)

    def info(self, *args, **kwargs):
        self._log(LogSeverity.INFO, *args, **kwargs)
    def warning(self, *args, **kwargs):
        self._log(LogSeverity.WARNING, *args, **kwargs)
    def error(self, *args, **kwargs):
        self._log(LogSeverity.ERROR, *args, **kwargs)
```

2. **Integration into runtime:** Wire `StructuredLogger` calls into:
- Risk gate `evaluate()` — log each intent with verdict and risk reason
- SimulatedAdapter — log submit, fill, reject, timeout, cancel
- ReconciliationEngine — log drift detection
- HealthReporter.health() — log system state changes

3. **`tests/operations/test_logging.py`**:
- Test JSON output format
- Test severity filtering
- Test correlation_id threading through risk → fill → reconcile
- Test missing fields don't crash

**Exit criteria:** `python -m pytest tests/operations/test_logging.py -v` passes. Vertical slice test produces JSON structured logs with correlation_ids.

---

### Task G3: Metrics emission from risk gate, execution, and portfolio

**Files:**
- Create: `src/titan/operations/metrics.py` — Counter, Gauge, Histogram, MetricsRegistry
- Modify: `src/titan/cli.py` — add `metrics dump` and `metrics health` commands
- Create: `tests/operations/test_metrics.py`

**What to build:**

1. **`src/titan/operations/metrics.py`**:
```python
"""In-memory metrics for TITAN operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


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
            name=self._name, value=self._value, tags=tags or {}, timestamp=datetime.now(timezone.utc).isoformat()
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
            name=self._name, value=value, tags=tags or {}, timestamp=datetime.now(timezone.utc).isoformat()
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

    def snapshot(self) -> dict[str, Any]:
        return {k: {"value": v.value, "tags": v.tags, "timestamp": v.timestamp} for k, v in self._metrics.items()}

    def dump_json(self) -> str:
        import json
        return json.dumps(self.snapshot(), default=str, indent=2)
```

2. **Wire metrics into runtime:**
- Risk gate evaluate() → increment `intents_evaluated`, `intents_rejected`
- Kill switch operations → increment `kill_switch_triggered`, `kill_switch_released`
- PortfolioEngine → gauge `positions_open`, `gross_exposure`, `cash_balance`
- SimulatedAdapter → increment `orders_submitted`, `orders_filled`, `orders_rejected`, `orders_cancelled`, `orders_unknown`
- Reconciliation → gauge `drift_count_warning`, `drift_count_critical`, `last_reconciliation_age_seconds`
- HealthReporter → gauge `system_state` (0=ACTIVE, 1=REDUCING, 2=HALTED, 3=DEGRADED)

3. **CLI commands:**
- `python -m titan.cli metrics dump` — print all metrics as JSON
- `python -m titan.cli metrics health` — assess from metrics: is risk working? orders progressing? broker truth match?

4. **`tests/operations/test_metrics.py`:**
- Counter increments correctly
- Gauge updates correctly
- Registry snapshot contains all metrics
- CLI output is valid JSON
- Multiple independent counters don't interfere

**Exit criteria:** `python -m pytest tests/operations/test_metrics.py -v` passes. After vertical slice, `titan.cli metrics dump` shows non-zero values.

---

### Task G4: FAILURE_MATRIX test coverage

**Files:**
- Create: `tests/failure_matrix/__init__.py`
- Create: `tests/failure_matrix/test_broker_timeout_submit.py`
- Create: `tests/failure_matrix/test_broker_timeout_cancel.py`
- Create: `tests/failure_matrix/test_duplicate_fill.py`
- Create: `tests/failure_matrix/test_event_store_write_failure.py`
- Create: `tests/failure_matrix/test_event_store_corruption.py`
- Create: `tests/failure_matrix/test_clock_drift.py`
- Create: `tests/failure_matrix/test_config_load_failure.py`

Each test should:
1. Set up the failure condition
2. Verify the system's expected behavior (reject, halt, alert, etc.)
3. Verify the recovery path (reconnect, reconcile, resume)
4. Use existing components (SimulatedAdapter, RiskGate, PortfolioEngine, ReconciliationEngine)

**Important:** Test the expected failure behavior and recovery path, not just that an error is thrown. Verify the system fails in a controlled way.

**Test fixture:** `tests/failure_matrix/conftest.py` can share common fixtures (RiskGate, PortfolioEngine, SimulatedAdapter, EventStore).

**Exit criteria:** `python -m pytest tests/failure_matrix/ -v` passes all 7 tests. FAILURE_MATRIX.md coverage increases from 3/14 to 10/14 rows.

---

### Task G5: Recovery automation — restart and reconcile

**Files:**
- Create: `src/titan/recovery/__init__.py`
- Create: `src/titan/recovery/restart.py` — recover_from_event_store(), reconcile_on_boot(), transition_on_boot()
- Create: `tests/recovery/test_restart.py` — integration tests
- Modify: `docs/runbooks/paper-session.md` — add restart section
- Modify: `docs/runbooks/incident.md` — add event store loss recovery

**What to build:**

1. **`src/titan/recovery/restart.py`:**
```python
"""Recovery automation for TITAN."""

from titan._core import EventStore, RiskGate, RiskConfig, PortfolioEngine, ReconciliationEngine, ReconciliationConfig


def recover_from_event_store(store: EventStore) -> tuple[RiskGate, PortfolioEngine]:
    """Rebuild system state from event store replay."""
    risk_gate = RiskGate(RiskConfig())
    portfolio = PortfolioEngine()
    # Replay all events and rebuild state
    # (for now: events carry the state transitions; full replay orchestration
    #  requires iterating events and applying them to each subsystem)
    return risk_gate, portfolio


def reconcile_on_boot(portfolio: PortfolioEngine, adapter, recon_engine: ReconciliationEngine) -> dict:
    """Compare rebuilt portfolio with adapter state, report drift."""
    # Collect adapter open positions
    # Compare with portfolio positions
    # Return reconciliation result
    return {}


def transition_on_boot(recon_result: dict) -> str:
    """Return 'ACTIVE' if clean, 'HALTED' if critical drift."""
    # Check critical drift
    # If clean → ACTIVE, else → HALTED
    return "ACTIVE"
```

2. **`titan.cli recovery restart`** — CLI command that calls `recover_from_event_store()`, `reconcile_on_boot()`, `transition_on_boot()`.

3. **Integration tests:**
- Record events in a session (submit intent, fill, update portfolio)
- Simulate restart: create fresh RiskGate + PortfolioEngine
- Run recovery: verify positions and risk state match pre-restart
- Inject drift before restart: verify system starts in HALTED

**Exit criteria:** `python -m pytest tests/recovery/test_restart.py -v` passes. `titan.cli recovery restart` replays events and reports system state. Runbooks updated.

---

### Task G6: Benchmark harness and performance baselines

**Files:**
- Create: `scripts/bench.py` — reusable benchmark runner
- Create: `knowledge/benchmarks/bench-risk-gate.md`
- Create: `knowledge/benchmarks/bench-event-store.md`
- Create: `knowledge/benchmarks/bench-replay.md`

**What to build:**

1. **`scripts/bench.py`** — A Python script that:
   - Accepts `--subsystem` (risk|event-store|replay), `--iterations`, `--seed`
   - Uses `time.perf_counter()` for latency measurement
   - Reports p50, p90, p99, p99.9 latency
   - Reports throughput (ops/s)
   - Outputs formatted results to stdout
   - Logs reproduction info (date, commit SHA, seed, params)

2. **Risk gate benchmark:** Create RiskGate with full config, call `evaluate()` 10,000 times with random valid intents. Measure per-call latency.

3. **Event store benchmark:** Create EventStore with SQLite, append 50,000 events sequentially, measure throughput and per-event latency.

4. **Replay benchmark:** Pre-populate 100k events, replay all, measure total time.

5. **Document results** in each `knowledge/benchmarks/bench-*.md` file.

**Exit criteria:** Three benchmark documents exist in `knowledge/benchmarks/` with measured results for all 12 PERFORMANCE_SPEC.md budgets. Any gaps between measured and budget are documented.
