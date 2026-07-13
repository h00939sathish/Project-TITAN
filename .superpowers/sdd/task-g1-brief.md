# Task G1: Kill-switch and trading-state persistence

## Goal

Make kill-switch state and trading state survive Python process restarts by persisting them to the event store and restoring on startup. Default to HALTED state if persisted state is unreadable or missing.

## Files to modify

- `core/src/messages.rs` — Add `RiskStateSnapshot` struct
- `core/src/risk.rs` — Add `persist_state()` and `restore_state()` to `RiskGate`
- `core/src/lib.rs` — Expose `RiskStateSnapshot` to Python
- Create: `tests/risk/test_state_persistence.py`

## Implementation details

### 1. Add `RiskStateSnapshot` to messages.rs

```rust
/// Snapshot of risk gate state for persistence across restarts.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RiskStateSnapshot {
    #[pyo3(get)]
    pub message_id: String,
    #[pyo3(get)]
    pub kill_switch_state: String,
    #[pyo3(get)]
    pub trading_state: String,
    #[pyo3(get)]
    pub occurred_at: String,
}
```

Add `to_json()`, `from_json()`, `__str__`, `__repr__` methods matching the pattern of other message types.

### 2. Add persist/restore methods to risk.rs

Add to `impl RiskGate`:

```rust
pub fn persist_state(&mut self, store: &event_store::EventStore) -> PyResult<()> {
    let snapshot = RiskStateSnapshot {
        message_id: format!("snap-{}", Uuid::now_v7()),
        kill_switch_state: format!("{:?}", self.kill_switch),
        trading_state: format!("{:?}", self.trading_state),
        occurred_at: Utc::now().to_rfc3339(),
    };
    let json = serde_json::to_string(&snapshot).map_err(|e| {
        PyRuntimeError::new_err(format!("Serialize error: {}", e))
    })?;
    let envelope = EventEnvelope::new(
        "RiskStateSnapshot".to_string(),
        "RiskGate".to_string(),
        "system".to_string(),
        "titan_core".to_string(),
        json,
        None, None, None,
    );
    store.append(&envelope)
}

pub fn restore_state(&mut self, store: &event_store::EventStore) -> PyResult<()> {
    let events = store.replay_by_type("RiskStateSnapshot")?;
    if let Some(latest) = events.last() {
        let snapshot: RiskStateSnapshot = serde_json::from_str(&latest.payload).map_err(|e| {
            PyRuntimeError::new_err(format!("Deserialize error: {}", e))
        })?;
        // Parse states and apply
        self.kill_switch = serde_json::from_str(&format!("\"{}\"", snapshot.kill_switch_state))
            .unwrap_or(KillSwitchState::Triggered); // fail-closed
        self.trading_state = serde_json::from_str(&format!("\"{}\"", snapshot.trading_state))
            .unwrap_or(TradingState::Halted); // fail-closed
    } else {
        // No persisted state — default to HALTED (fail-closed)
        self.kill_switch = KillSwitchState::Triggered;
        self.trading_state = TradingState::Halted;
    }
    Ok(())
}

/// Factory method: create RiskGate from persisted state, or default to HALTED.
#[staticmethod]
pub fn load_or_default(config: RiskConfig, store: &event_store::EventStore) -> PyResult<RiskGate> {
    let mut gate = RiskGate::new(config);
    let events = store.replay_by_type("RiskStateSnapshot")?;
    if let Some(latest) = events.last() {
        let snapshot: RiskStateSnapshot = serde_json::from_str(&latest.payload).map_err(|e| {
            PyRuntimeError::new_err(format!("Deserialize error: {}", e))
        })?;
        gate.kill_switch = serde_json::from_str(&format!("\"{}\"", snapshot.kill_switch_state))
            .unwrap_or(KillSwitchState::Triggered);
        gate.trading_state = serde_json::from_str(&format!("\"{}\"", snapshot.trading_state))
            .unwrap_or(TradingState::Halted);
    } else {
        // No state found — default to HALTED for safety
        gate.kill_switch = KillSwitchState::Triggered;
        gate.trading_state = TradingState::Halted;
    }
    Ok(gate)
}
```

You need to add the necessary imports to risk.rs:
```rust
use crate::event_store;
use crate::messages::{EventEnvelope, RiskStateSnapshot};
use chrono::Utc;
use uuid::Uuid;
use pyo3::exceptions::PyRuntimeError;
```

### 3. Expose in lib.rs

```rust
m.add_class::<messages::RiskStateSnapshot>()?;
```

### 4. Rust tests (add to risk.rs test module)

```rust
#[test]
fn test_persist_and_restore_state() {
    use crate::event_store::EventStore;
    let store = EventStore::new(":memory:").unwrap();
    let mut gate = RiskGate::new(RiskConfig::default());
    // Initially active/armed
    assert_eq!(gate.trading_state, TradingState::Active);
    assert_eq!(gate.kill_switch, KillSwitchState::Armed);
    // Trigger kill switch
    gate.trigger_kill_switch().unwrap();
    assert_eq!(gate.kill_switch, KillSwitchState::Triggered);
    // Persist
    gate.persist_state(&store).unwrap();
    // Restore in a new gate
    let restored = RiskGate::load_or_default(RiskConfig::default(), &store).unwrap();
    assert_eq!(restored.kill_switch, KillSwitchState::Triggered);
    assert_eq!(restored.trading_state, TradingState::Halted);
}

#[test]
fn test_restore_defaults_to_halted_when_no_state() {
    use crate::event_store::EventStore;
    let store = EventStore::new(":memory:").unwrap();
    let gate = RiskGate::load_or_default(RiskConfig::default(), &store).unwrap();
    assert_eq!(gate.kill_switch, KillSwitchState::Triggered);
    assert_eq!(gate.trading_state, TradingState::Halted);
}
```

### 5. Python tests (tests/risk/test_state_persistence.py)

```python
"""Tests for risk gate state persistence."""

import pytest
from titan._core import RiskGate, RiskConfig, EventStore, TradingState, KillSwitchState


class TestRiskStatePersistence:
    def test_persist_and_restore_kill_switch(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.kill_switch == KillSwitchState.Triggered

    def test_persist_and_restore_trading_state(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.set_trading_state(TradingState.Halted)
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.trading_state == TradingState.Halted

    def test_defaults_to_halted_with_no_state(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate.load_or_default(config, store)
        assert gate.kill_switch == KillSwitchState.Triggered
        assert gate.trading_state == TradingState.Halted
        # Verify routing is blocked
        assert not gate.trading_state.accepts_intents()

    def test_persisted_state_halts_routing(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        # Verify routing is blocked after restore
        assert restored.kill_switch.blocks_routing()
        assert not restored.trading_state.accepts_intents()

    def test_multiple_persists_restores_latest(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        # Persist active state
        gate.persist_state(store)
        # Then trigger kill and persist again
        gate.trigger_kill_switch()
        gate.persist_state(store)
        # Should restore the latest (triggered)
        restored = RiskGate.load_or_default(config, store)
        assert restored.kill_switch == KillSwitchState.Triggered
```

## Acceptance criteria

- `cd core && cargo test` passes (62 + 2 new = 64 Rust tests)
- `python -m pytest tests/risk/test_state_persistence.py -v` passes all 5 tests
- `python -m pytest tests/ -v` passes (118 + 5 = 123 Python tests)
- Kill switch and trading state survive event store persistence round-trip
- Default to HALTED/Triggered when no state exists

## Constraints

- Follow existing Rust code patterns (error handling, PyO3 decorators, test style)
- No breaking changes to existing RiskGate API
- No credentials in source code
