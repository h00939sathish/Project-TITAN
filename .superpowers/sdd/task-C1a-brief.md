### Task C1a: Rust risk types — TradingState, KillSwitchState, RiskConfig

**Files:**
- Create: `core/src/risk.rs` (top portion — types only)
- Modify: `core/src/lib.rs` (register types with PyO3)

**Interfaces:**
- Consumes: `crate::types::Money` (already exists in `core/src/types.rs`)
- Produces: `TradingState` enum, `KillSwitchState` enum, `RiskConfig` struct, `RiskReasonCode` enum — all with PyO3 bindings and pure-Rust state machine methods

**What to build:**

1. **`TradingState`** enum with variants: `Active`, `Reducing`, `Halted`. Must have:
   - `transition(&mut self, target: TradingState) -> Result<(), String>` with these valid transitions:
     - Active → Reducing, Active → Halted
     - Reducing → Halted
     - Halted → Active, Halted → Reducing
   - `accepts_intents(&self) -> bool` (only Active)
   - `#[pyclass(eq, eq_int)]` + `#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]`
   - `#[pymethods]`: `__str__`, `__repr__`, `is_active()` (calls accepts_intents)

2. **`KillSwitchState`** enum with variants: `Armed`, `Triggered`, `Releasing`, `Released`. Must have:
   - `transition(&mut self, target: KillSwitchState) -> Result<(), String>` with these valid transitions:
     - Armed → Triggered
     - Triggered → Releasing
     - Releasing → Released, Releasing → Triggered
     - Released → Armed
   - `is_triggered(&self) -> bool` (Triggered)
   - `blocks_routing(&self) -> bool` (Triggered or Releasing)
   - Same derives and PyO3 methods as TradingState

3. **`RiskConfig`** struct with fields (all `#[pyo3(get, set)]`):
   - `instrument_eligibility: Vec<String>`
   - `max_order_notional: Money`
   - `max_order_quantity: u64`
   - `max_position_size: u64`
   - `max_gross_exposure: Money`
   - `max_drawdown_fraction: f64`
   - `max_daily_loss: Money`
   - `data_freshness_threshold_ms: u64`
   - `#[pyclass]` + Default impl (values: 1M USD notional, 10k qty, 50k pos, 10M exposure, 0.10 drawdown, 50k daily loss, 5000ms freshness)

4. **`RiskReasonCode`** enum with variants (all `Clone, Copy, Debug, PartialEq, Serialize, Deserialize, #[pyclass(eq, eq_int)]`):
   - `NotRoutable`, `InstrumentNotEligible`, `DataStale`, `OrderNotionalExceeded`, `OrderQuantityExceeded`, `PositionLimitExceeded`, `GrossExposureExceeded`, `DrawdownExceeded`, `DailyLossExceeded`, `TradingHalted`, `KillSwitchTriggered`, `InternalError`

5. **Rust unit tests** in `core/src/risk.rs` testing:
   - All valid trading state transitions
   - Illegal trading state transitions (e.g., Reducing → Active)
   - Kill switch state machine
   - Kill switch no auto-reset (Triggered → Armed illegal)
   - RiskConfig defaults

6. **Register** in `core/src/lib.rs`:
   - `pub mod risk;`
   - Add these classes to the `_core` pymodule: `TradingState`, `KillSwitchState`, `RiskConfig`, `RiskReasonCode`

**Important implementation notes:**
- `thiserror::Error` is already in Cargo.toml dependencies
- serde, pyo3 are already available
- Use `use crate::types::Money;` — Money is already defined
- The `transition()` methods should be pure Rust (not in `#[pymethods]`) — they return `Result<(), String>`
- Only `__str__`, `__repr__`, and `is_active()` on TradingState go in `#[pymethods]`
- For RiskConfig, the `#[new]` constructor takes all 8 args; also add `Default` impl

**TDD required:** Write failing tests first, then implement to make them pass.
