### Task C1b: Rust RiskGate pipeline with all evaluation checks

**Files:**
- Modify: `core/src/risk.rs` (add `RiskVerdict`, `RiskGate` struct, evaluation pipeline)
- Modify: `core/src/lib.rs` (register new types with PyO3)

**Interfaces:**
- Consumes: `crate::messages::TradeIntent` (message_id, instrument_id, side, quantity, price, etc.), `RiskConfig`, `TradingState`, `KillSwitchState`, `RiskReasonCode`, `crate::types::Money`
- Produces: `RiskVerdict` (accepted: bool, reason: Option<RiskReasonCode>, reason_detail: String), `RiskGate` (with evaluate method)

**What to build:**

1. **`RiskVerdict` struct** (`#[pyclass]`, `#[derive(Clone, Debug)]`):
   - `accepted: bool` (`#[pyo3(get)]`)
   - `reason: Option<RiskReasonCode>` (`#[pyo3(get)]`)
   - `reason_detail: String` (`#[pyo3(get)]`)

2. **`RiskGate` struct** (`#[pyclass]`, `#[derive(Clone, Debug)]`):
   - Fields: `config: RiskConfig`, `trading_state: TradingState`, `kill_switch: KillSwitchState` (all `#[pyo3(get, set)]`)
   - `#[new]` constructor: `pub fn new(config: RiskConfig) -> Self`

3. **`evaluate(&self, intent: &TradeIntent, current_position_size: Option<u64>, current_gross_exposure: Option<&Money>, current_drawdown: Option<f64>, current_daily_loss: Option<&Money>) -> RiskVerdict`** — the pipeline:

   The pipeline runs these checks **in order**, short-circuiting on first rejection:
   
   a. **Kill switch check** — if `kill_switch.blocks_routing()`, reject with `KillSwitchTriggered`
   b. **Trading state check** — if `!trading_state.accepts_intents()`, reject with `TradingHalted`
   c. **Instrument eligibility** — if `config.instrument_eligibility` is non-empty AND intent's instrument_id not in it, reject with `InstrumentNotEligible`
   d. **Order limits — notional** — compute notional = quantity * price. Since Money doesn't have Mul yet, compute: `intent.quantity as i64 * intent.price.amount()`, compare to `config.max_order_notional.amount()`. If exceeded, reject with `OrderNotionalExceeded`
   e. **Order limits — quantity** — if `intent.quantity > config.max_order_quantity`, reject with `OrderQuantityExceeded`
   f. **Position/exposure limits** — if `current_position_size` is Some:
      - If `current_position_size.unwrap() > config.max_position_size`, reject with `PositionLimitExceeded`
   g. **Gross exposure check** — if `current_gross_exposure` is Some:
      - If `current_gross_exposure.unwrap().amount() > config.max_gross_exposure.amount()`, reject with `GrossExposureExceeded`
   h. **Drawdown check** — if `current_drawdown` is Some:
      - If `current_drawdown.unwrap() > config.max_drawdown_fraction`, reject with `DrawdownExceeded`
   i. **Daily loss check** — if `current_daily_loss` is Some:
      - If `current_daily_loss.unwrap().amount() > config.max_daily_loss.amount()`, reject with `DailyLossExceeded`
   
   If all checks pass, return `RiskVerdict { accepted: true, reason: None, reason_detail: "".to_string() }`

4. **Kill switch / trading state methods** on `RiskGate`:
   - `set_trading_state(&mut self, state: TradingState) -> PyResult<()>` — delegates to `TradingState::transition()`, maps error to `PyValueError`
   - `trigger_kill_switch(&mut self) -> PyResult<()>` — transitions kill switch from Armed → Triggered, maps error to `PyValueError`
   - `release_initiated(&mut self) -> PyResult<()>` — transitions Triggered → Releasing
   - `release_completed(&mut self) -> PyResult<()>` — transitions Releasing → Released
   - These should all be `#[pymethods]`

5. **Rust unit tests** in `core/src/risk.rs` that test:
   - Gate accepts valid TradeIntent with default config (no position data)
   - Gate rejects when kill switch is triggered
   - Gate rejects when trading state is Halted
   - Gate rejects when instrument not in eligibility list
   - Gate rejects when notional exceeds max
   - Gate rejects when quantity exceeds max
   - Gate rejects when position size exceeds max (with current_position_size=Some)
   - Gate rejects when gross exposure exceeds max
   - Gate rejects when drawdown exceeded
   - Gate rejects when daily loss exceeded
   - Gate triggers kill switch successfully
   - Gate sets trading state successfully
   - Gate transitions through kill switch lifecycle (trigger → release initiated → release completed)

**Important notes:**
- `TradeIntent` fields: `message_id: String`, `correlation_id: String`, `instrument_id: String`, `side: Side` (Buy/Sell), `quantity: u64`, `price: Money`, `order_type: String`, `time_in_force: String`
- `Side` is in `types.rs` with variants `Buy`, `Sell`
- Money fields: `.amount()` returns `i64`, `.currency()` returns `&str`
- For the eligibility check, compare `intent.instrument_id` (String) against each entry in `config.instrument_eligibility`
- When instrument_eligibility is empty, all instruments are eligible (skip the check)

**TDD required.**

