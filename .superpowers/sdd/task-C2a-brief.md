### Task C2a: Rust portfolio projection — positions, cash, PnL

**Files:**
- Create: `core/src/portfolio.rs`
- Modify: `core/src/lib.rs` (register types with PyO3)

**Interfaces:**
- Consumes: `crate::types::Money, Quantity, Price, InstrumentId, Side`, `crate::messages::EventEnvelope`
- Produces: `PositionState` enum, `Position` struct, `PortfolioEngine` with `apply_fill()` and snapshot methods

**What to build:**

1. **`PositionState` enum** — position lifecycle per spec (Portfolio.spec.md Mermaid diagram):
   ```
   FLAT → LONG (buy fill)
   FLAT → SHORT (sell fill)
   LONG → LONG (additional buy)
   LONG → FLAT (sell to zero)
   LONG → SHORT (sell exceeds long — if allowed)
   SHORT → SHORT (additional sell)
   SHORT → FLAT (buy to zero)
   SHORT → LONG (buy exceeds short)
   ```
   - Variants: `Flat`, `Long(u64)`, `Short(u64)`  (u64 = quantity held)
   - `#[pyclass(eq, eq_int)]` — wait, `Long(u64)` has data so `eq_int` won't work. Use regular `#[pyclass]` with `#[derive(Clone, Debug, PartialEq)]`
   - Actually, PyO3 enums with data need `#[pyclass]` with `from_py_object`. Let's use a different approach:

   **Use a struct-based approach** instead of a data-carrying enum for PyO3 compatibility:
   
   ```rust
   #[pyclass]
   #[derive(Clone, Debug, Default, PartialEq)]
   pub struct Position {
       pub instrument_id: String,
       pub side: PositionSide,
       pub quantity: u64,
       pub cost_basis: Money,
   }
   
   #[pyclass(eq, eq_int)]
   #[derive(Clone, Copy, Debug, Default, PartialEq)]
   pub enum PositionSide {
       #[default]
       Flat,
       Long,
       Short,
   }
   ```

2. **`PortfolioEngine`** struct (`#[pyclass]`, `#[derive(Clone, Debug)]`):
   - Fields:
     - `positions: HashMap<String, Position>` (keyed by instrument_id string)
     - `cash_balance: Money`
     - `base_currency: String`
   - `#[new]` constructor: takes `base_currency: &str`, `initial_cash: Money`
   - `#[pymethods]` methods:

3. **`apply_fill(&mut self, instrument_id: &str, side: &str, quantity: u64, price: &Money) -> PyResult<()>`**:
   - Parses side: "buy" or "sell" (case-insensitive)
   - Gets or creates the Position for this instrument_id
   - Implements the position lifecycle:
     - **Buy fill:**
       - If Flat → Long(quantity), cost_basis = price * quantity
       - If Long(existing_qty) → Long(existing_qty + quantity), update cost_basis as weighted average: `(cost_basis * existing_qty + price * quantity) / (existing_qty + quantity)`
       - If Short(existing_qty):
         - If quantity < existing_qty: reduce position to Short(existing_qty - quantity), realize PnL = (cost_basis - price) * quantity
         - If quantity == existing_qty: go Flat, realize PnL = (cost_basis - price) * quantity
         - If quantity > existing_qty: go Long(quantity - existing_qty), realize PnL = (cost_basis - price) * existing_qty
     - **Sell fill:**
       - Mirror logic of buy fill (Long ←→ Short, cost_basis calculations reversed)
   - Updates cash_balance: `cash_balance -= price * quantity` for buys, `cash_balance += price * quantity` for sells
   
   Keep it simple — use integer arithmetic with Money. Don't worry about fractional calculations for now.

4. **Snapshot / query methods**:
   - `get_position(&self, instrument_id: &str) -> Option<Position>` — get position for an instrument
   - `get_cash_balance(&self) -> Money` — return current cash
   - `get_realized_pnl(&self) -> Money` — sum of all realized PnL so far
   - `get_unrealized_pnl(&self, instrument_id: &str, current_price: &Money) -> PyResult<Money>` — (position quantity * (current_price - avg_cost))
   - `total_gross_exposure(&self) -> Money` — sum of |position_quantity * last_price| across all positions
   - `get_snapshot(&self) -> PortfolioSnapshot` — returns a PortfolioSnapshot (defined in risk.rs, but for now define it locally or use a compatible struct)

   Wait — PortfolioSnapshot is defined in risk.rs (Task C1b). To avoid a dependency cycle, **define PortfolioSnapshot in this module** and have a method that creates one. The risk module will import it from here. Let me adjust the plan:

   **Define `PortfolioSnapshot` in portfolio.rs** with:
   - `gross_exposure: Money`
   - `drawdown_fraction: f64` (0.0 for now — drawdown tracking comes later)
   - `daily_realized_loss: Money` (0.0 for now — daily tracking comes later)
   - `position_size: u64` (for the instrument being checked)
   - All fields `#[pyo3(get, set)]`

   Then the RiskGate in C1b will import `PortfolioSnapshot` from `crate::portfolio::PortfolioSnapshot`.

   **Update C1b note:** The RiskGate.evaluate() takes `Option<&PortfolioSnapshot>` where `PortfolioSnapshot` is defined in `crate::portfolio`.

5. **Rust unit tests** in `core/src/portfolio.rs`:
   - `test_buy_open_long` — buy 100, position is Long(100)
   - `test_sell_open_short` — sell 100 from flat, position is Short(100)
   - `test_buy_add_to_long` — buy 100, then buy 50 → Long(150)
   - `test_sell_reduce_long_to_flat` — buy 100, sell 100 → Flat
   - `test_sell_reduce_long_to_short` — buy 100, sell 150 → Short(50)
   - `test_buy_reduce_short_to_flat` — sell 100, buy 100 → Flat
   - `test_buy_reduce_short_to_long` — sell 100, buy 150 → Long(50)
   - `test_cash_balance_updates` — verify cash goes down on buys, up on sells
   - `test_realized_pnl` — buy at 100, sell at 110, verify profit
   - `test_gross_exposure` — multiple positions sum correctly
   - `test_get_position_not_found` — returns None
   - `test_get_snapshot` — returns correct snapshot data

**Important notes:**
- Use `std::collections::HashMap` for positions
- Money multiplication: compute `Money(amount * quantity as i64, currency)` — simplest approach
- Money subtraction/comparison: compare `.amount()` values directly (same currency)
- For the weighted average cost basis, compute using integer arithmetic: `(old_cost * old_qty + new_price * new_qty) / (old_qty + new_qty)` — using i64, potential overflow is acceptable for MVP

**TDD required.**

**Existing code to reference:**
- `core/src/types.rs` — Money(amount: i64, currency: String), Side(Buy/Sell)
- Money fields: `amount()` returns i64, `currency()` returns &str
