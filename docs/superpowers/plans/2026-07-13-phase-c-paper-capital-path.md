# Phase C — Deterministic Paper Capital Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the fail-closed risk gate, kill switch, portfolio projection, reconciliation engine, and simulated execution — the deterministic pipeline from `TradeIntent → RiskDecision → ApprovedOrderIntent → simulated fill → portfolio update → reconcile`.

**Architecture:** All safety-critical logic lives in Rust (`risk.rs`, `kill_switch.rs`, `portfolio.rs`, `reconciliation.rs`) compiled via PyO3. Python holds the config loader (`src/titan/risk/limits.py`) and simulated adapter (`src/titan/execution/simulated_adapter.py`). Each Rust module exposes its types and methods to Python for testing.

**Tech Stack:** Rust 1.80+ (edition 2024), PyO3 0.29, serde, thiserror, Python 3.14, pytest, ruff, mypy, clippy.

## Global Constraints

- Risk gate is the sole path from `TradeIntent` to `ApprovedOrderIntent` — no bypass allowed.
- Kill-switch state is persistent, fail-closed, manually released.
- All decisions are immutable events persisted to the SQLite event store.
- Portfolio projection is event-driven (reads OrderFilled, CorporateAction events).
- Reconciliation compares broker truth to internal projection; drift beyond threshold triggers halt.
- No AI component has any risk, portfolio, or execution authority.
- Every check runs in Rust; Python configures but does not decide.
- p99 latency budgets per PERFORMANCE_SPEC.md: risk gate <50 μs, kill switch <10 μs.

---

### Task C1a: Rust risk types — TradingState, KillSwitchState, RiskConfig

**Files:**
- Create: `core/src/risk.rs` (top portion — types only)
- Create: `tests/core/test_risk_types_rust.rs` (Rust unit tests)

**Interfaces:**
- Consumes: nothing new
- Produces: `TradingState` enum, `KillSwitchState` enum, `RiskConfig` struct, `RiskCheck` enum with reason codes

- [ ] **Step 1: Write the failing Rust test for trading state transitions**

In `core/src/risk.rs`, add a `#[cfg(test)] mod tests` block. Write tests that verify:
- ACTIVE rejects REDUCING as a starting state (no, that's wrong)
- Actually: ACTIVE -> REDUCING, ACTIVE -> HALTED, REDUCING -> HALTED are valid
- HALTED -> ACTIVE, HALTED -> REDUCING are valid
- REDUCING -> ACTIVE, HALTED -> New are not

Wait — this is defined in risk.spec.md. Let me use a pure-Rust approach:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trading_state_transitions() {
        // ACTIVE -> REDUCING -> HALTED
        let mut s = TradingState::Active;
        assert!(s.transition(TradingState::Reducing).is_ok());
        assert!(s.transition(TradingState::Halted).is_ok());
        // HALTED -> ACTIVE (with reconciliation)
        assert!(s.transition(TradingState::Active).is_ok());
    }

    #[test]
    fn test_trading_state_illegal() {
        let mut s = TradingState::Active;
        assert!(s.transition(TradingState::Halted).is_ok());
        // HALTED -> REDUCING is valid per spec
        assert!(s.transition(TradingState::Reducing).is_ok());
        // REDUCING -> ACTIVE is NOT valid per spec
        assert!(s.transition(TradingState::Active).is_err());
    }

    #[test]
    fn test_kill_switch_state_machine() {
        // ARMED -> TRIGGERED -> RELEASING -> RELEASED -> ARMED
        let mut ks = KillSwitchState::Armed;
        assert!(ks.transition(KillSwitchState::Triggered).is_ok());
        assert!(ks.transition(KillSwitchState::Releasing).is_ok());
        assert!(ks.transition(KillSwitchState::Released).is_ok());
        assert!(ks.transition(KillSwitchState::Armed).is_ok());
    }

    #[test]
    fn test_kill_switch_no_auto_reset() {
        let mut ks = KillSwitchState::Armed;
        assert!(ks.transition(KillSwitchState::Triggered).is_ok());
        // TRIGGERED -> ARMED is illegal (must go through RELEASING -> RELEASED)
        assert!(ks.transition(KillSwitchState::Armed).is_err());
    }

    #[test]
    fn test_risk_config_defaults() {
        let cfg = RiskConfig::default();
        assert_eq!(cfg.max_order_notional.to_string(), "1000000");
        assert_eq!(cfg.max_drawdown_fraction, 0.10);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --lib risk::tests`
Expected: compilation error (module not found or types not defined)

- [ ] **Step 3: Implement Rust types in `core/src/risk.rs`**

```rust
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::types::Money;

// ── Trading state ──────────────────────────────────────────────

#[pyclass(eq, eq_int)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum TradingState {
    #[default]
    Active,
    Reducing,
    Halted,
}

impl TradingState {
    pub fn transition(&mut self, target: TradingState) -> Result<(), String> {
        let from = *self;
        let valid = match (from, target) {
            (TradingState::Active, TradingState::Reducing) => true,
            (TradingState::Active, TradingState::Halted) => true,
            (TradingState::Reducing, TradingState::Halted) => true,
            (TradingState::Halted, TradingState::Active) => true,
            (TradingState::Halted, TradingState::Reducing) => true,
            _ => false,
        };
        if valid {
            *self = target;
            Ok(())
        } else {
            Err(format!("Illegal trading state transition: {:?} -> {:?}", from, target))
        }
    }

    pub fn accepts_intents(&self) -> bool {
        matches!(self, TradingState::Active)
    }
}

// ── Kill switch state ──────────────────────────────────────────

#[pyclass(eq, eq_int)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum KillSwitchState {
    #[default]
    Armed,
    Triggered,
    Releasing,
    Released,
}

impl KillSwitchState {
    pub fn transition(&mut self, target: KillSwitchState) -> Result<(), String> {
        let from = *self;
        let valid = match (from, target) {
            (KillSwitchState::Armed, KillSwitchState::Triggered) => true,
            (KillSwitchState::Triggered, KillSwitchState::Releasing) => true,
            (KillSwitchState::Releasing, KillSwitchState::Released) => true,
            (KillSwitchState::Releasing, KillSwitchState::Triggered) => true,
            (KillSwitchState::Released, KillSwitchState::Armed) => true,
            _ => false,
        };
        if valid {
            *self = target;
            Ok(())
        } else {
            Err(format!("Illegal kill-switch transition: {:?} -> {:?}", from, target))
        }
    }

    pub fn is_triggered(&self) -> bool {
        matches!(self, KillSwitchState::Triggered)
    }

    pub fn blocks_routing(&self) -> bool {
        matches!(self, KillSwitchState::Triggered | KillSwitchState::Releasing)
    }
}

// ── Risk configuration ─────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RiskConfig {
    #[pyo3(get, set)]
    pub instrument_eligibility: Vec<String>,
    #[pyo3(get, set)]
    pub max_order_notional: Money,
    #[pyo3(get, set)]
    pub max_order_quantity: u64,
    #[pyo3(get, set)]
    pub max_position_size: u64,
    #[pyo3(get, set)]
    pub max_gross_exposure: Money,
    #[pyo3(get, set)]
    pub max_drawdown_fraction: f64,
    #[pyo3(get, set)]
    pub max_daily_loss: Money,
    #[pyo3(get, set)]
    pub data_freshness_threshold_ms: u64,
}

#[pymethods]
impl RiskConfig {
    #[new]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        instrument_eligibility: Vec<String>,
        max_order_notional: Money,
        max_order_quantity: u64,
        max_position_size: u64,
        max_gross_exposure: Money,
        max_drawdown_fraction: f64,
        max_daily_loss: Money,
        data_freshness_threshold_ms: u64,
    ) -> Self {
        Self {
            instrument_eligibility,
            max_order_notional,
            max_order_quantity,
            max_position_size,
            max_gross_exposure,
            max_drawdown_fraction,
            max_daily_loss,
            data_freshness_threshold_ms,
        }
    }
}

impl Default for RiskConfig {
    fn default() -> Self {
        Self {
            instrument_eligibility: Vec::new(),
            max_order_notional: Money::new(1_000_000, "USD"),
            max_order_quantity: 10_000,
            max_position_size: 50_000,
            max_gross_exposure: Money::new(10_000_000, "USD"),
            max_drawdown_fraction: 0.10,
            max_daily_loss: Money::new(50_000, "USD"),
            data_freshness_threshold_ms: 5_000,
        }
    }
}

// ── Reason codes ───────────────────────────────────────────────

#[pyclass(eq, eq_int)]
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum RiskReasonCode {
    NotRoutable,
    InstrumentNotEligible,
    DataStale,
    OrderNotionalExceeded,
    OrderQuantityExceeded,
    PositionLimitExceeded,
    GrossExposureExceeded,
    DrawdownExceeded,
    DailyLossExceeded,
    TradingHalted,
    KillSwitchTriggered,
    InternalError,
}

// ── PyO3 exports ───────────────────────────────────────────────

#[pymethods]
impl TradingState {
    fn __str__(&self) -> String { format!("{:?}", self) }
    fn __repr__(&self) -> String { format!("TradingState.{:?}", self) }
    pub fn is_active(&self) -> bool { self.accepts_intents() }
}

#[pymethods]
impl KillSwitchState {
    fn __str__(&self) -> String { format!("{:?}", self) }
    fn __repr__(&self) -> String { format!("KillSwitchState.{:?}", self) }
}

#[pymethods]
impl RiskReasonCode {
    fn __str__(&self) -> String { format!("{:?}", self) }
    fn __repr__(&self) -> String { format!("RiskReasonCode.{:?}", self) }
}
```

- [ ] **Step 4: Register module in `core/src/lib.rs`**

Add `pub mod risk;` and register `TradingState`, `KillSwitchState`, `RiskConfig`, `RiskReasonCode` with PyO3.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cargo test --lib risk::tests`
Expected: 5 tests pass

- [ ] **Step 6: Commit**

---

### Task C1b: Rust RiskGate pipeline with all checks

**Files:**
- Modify: `core/src/risk.rs` (add `RiskGate` struct, `RiskDecision` output, evaluation pipeline)

**Interfaces:**
- Consumes: `TradeIntent`, `RiskConfig`, `TradingState`, `KillSwitchState`, portfolio snapshot
- Produces: `RiskGate` with `evaluate()` -> `RiskVerdict` (accepted/rejected + reason code)

- [ ] **Step 1: Write failing Rust tests**

Add to `core/src/risk.rs`:
```rust
#[test]
fn test_risk_gate_rejects_when_halted() {
    let config = RiskConfig::default();
    let mut gate = RiskGate::new(config);
    gate.trading_state = TradingState::Halted;
    let intent = TradeIntent { /* minimal valid */ };
    let verdict = gate.evaluate(&intent, None);
    assert!(!verdict.accepted);
    assert_eq!(verdict.reason, Some(RiskReasonCode::TradingHalted));
}
```

- [ ] **Step 2: Implement `RiskGate`**

```rust
#[pyclass]
#[derive(Clone, Debug)]
pub struct RiskGate {
    #[pyo3(get, set)]
    pub config: RiskConfig,
    #[pyo3(get)]
    pub trading_state: TradingState,
    #[pyo3(get)]
    pub kill_switch: KillSwitchState,
}

#[pymethods]
impl RiskGate {
    #[new]
    pub fn new(config: RiskConfig) -> Self;
    pub fn evaluate(&self, intent: &TradeIntent, portfolio: Option<&PortfolioSnapshot>) -> RiskVerdict;
    pub fn set_trading_state(&mut self, state: TradingState) -> PyResult<()>;
    pub fn trigger_kill_switch(&mut self) -> PyResult<()>;
    pub fn release_kill_switch(&mut self) -> PyResult<()>;
}
```

The `evaluate()` method runs the pipeline:
1. Kill switch check → blocks if triggered
2. Trading state check → blocks if not Active
3. Instrument eligibility
4. Data freshness (intent timestamp vs now)
5. Order limits (notional, quantity)
6. Position/exposure limits (if portfolio provided)
7. Drawdown check
8. Daily loss check

- [ ] **Step 3: Add Python tests**
- [ ] **Step 4: Wire into lib.rs**
- [ ] **Step 5: Full test pass**

---

### Task C1c: Kill switch persistence and CLI

**Files:**
- Create: `src/titan/risk/limits.py`
- Create: `src/titan/risk/__init__.py`
- Create: `tests/risk/test_gate.py`
- Create: `tests/risk/test_kill_switch.py`
- Modify: `src/titan/cli.py` (add risk commands)

- [ ] **Step 1-5**: Implement Python risk config loader, CLI commands for kill switch, operator release

---

### Task C2a: Rust portfolio projection

**Files:**
- Create: `core/src/portfolio.rs`
- Create: `tests/core/test_portfolio_rust.rs`

---

### Task C2b: Rust reconciliation engine

**Files:**
- Create: `core/src/reconciliation.rs`
- Create: `tests/core/test_reconciliation_rust.rs`

---

### Task C2c: Python simulated adapter + integration test

**Files:**
- Create: `src/titan/execution/__init__.py`
- Create: `src/titan/execution/simulated_adapter.py`
- Create: `tests/integration/test_paper_vertical_slice.py`

---

## File Structure (final)

```
core/src/
  risk.rs              # RiskGate, TradingState, KillSwitchState, RiskConfig, RiskVerdict
  portfolio.rs         # Portfolio, Position, CashBalance, PnL calculation
  reconciliation.rs    # ReconciliationEngine, drift comparison
src/titan/
  risk/
    __init__.py
    limits.py          # Python config loader → RiskConfig
  execution/
    __init__.py
    simulated_adapter.py
tests/
  risk/
    test_gate.py
    test_kill_switch.py
  integration/
    test_paper_vertical_slice.py
```
