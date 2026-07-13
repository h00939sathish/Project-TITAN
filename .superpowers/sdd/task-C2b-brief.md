### Task C2b: Rust reconciliation engine

**Files:**
- Create: `core/src/reconciliation.rs`
- Modify: `core/src/lib.rs` (register new types with PyO3)

**Interfaces:**
- Consumes: `crate::portfolio::PortfolioEngine`, `crate::portfolio::PortfolioSnapshot`, `crate::types::Money`
- Produces: `ReconciliationDrift` enum (Critical, Warning, InSync), `ReconciliationEngine` struct

**What to build:**

1. **`ReconciliationDriftSeverity`** enum (`#[pyclass(eq, eq_int)]`):
   - `InSync` — no drift or within warning threshold
   - `Warning` — small drift below critical threshold
   - `Critical` — drift exceeds critical threshold

2. **`PositionDrift`** struct (`#[pyclass]`):
   - `instrument_id: String` — which instrument
   - `expected_side: String` — "LONG"/"SHORT"/"FLAT" from portfolio
   - `expected_quantity: i64` — signed (+ for long, - for short, 0 for flat)
   - `actual_side: String` — from broker
   - `actual_quantity: i64` — from broker
   - `quantity_drift: i64` — absolute difference

3. **`ReconciliationResult`** struct (`#[pyclass]`):
   - `severity: ReconciliationDriftSeverity`
   - `position_drifts: Vec<PositionDrift>` — per-instrument differences
   - `cash_expected: Money`
   - `cash_actual: Money`
   - `cash_drift: Money`
   - `summary: String` — human-readable summary

4. **`ReconciliationConfig`** struct (`#[pyclass]`):
   - `critical_drift_fraction: f64` — default 0.05 (5%)
   - `warning_drift_fraction: f64` — default 0.01 (1%)

5. **`ReconciliationEngine`** struct (`#[pyclass]`):

   Methods:
   - `#[new]` — takes `config: Option<ReconciliationConfig>`, defaults to 5%/1%
   - `compare(portfolio: &PortfolioEngine, broker_positions: Vec<BrokerPosition>, broker_cash: &Money) -> ReconciliationResult`

6. **`BrokerPosition`** struct (`#[pyclass]`):
   - `instrument_id: String`
   - `side: String` — "LONG"/"SHORT"/"FLAT"
   - `quantity: i64`
   These represent what the broker reports, fed in from Python tests.

7. **Compare logic**:
   - For each position in the portfolio:
     - Find matching broker position by instrument_id
     - Compute signed quantities: portfolio = +qty for long, -qty for short, 0 for flat; broker = +qty for long, -qty for short
     - If no matching broker position, treat as quantity=0 (broker doesn't know about it)
   - For each broker position not in portfolio, treat as unknown position (portfolio doesn't know about it)
   - Compute cash drift: abs(portfolio.cash_balance.amount - broker_cash.amount)
   - Determine severity:
     - If any position drift > critical_drift_fraction of position size OR cash drift > critical_drift_fraction → Critical
     - If any drift > warning_drift_fraction → Warning
     - Else → InSync

   Keep it simple: compare string amounts directly. No complex floating point.

8. **Rust unit tests**:
   - `test_in_sync` — portfolio and broker match exactly
   - `test_small_position_drift_warning` — small difference triggers warning
   - `test_large_position_drift_critical` — large difference triggers critical
   - `test_cash_drift_critical` — cash mismatch triggers critical
   - `test_broker_has_unknown_position` — broker has position portfolio doesn't know about
   - `test_portfolio_has_unknown_position` — portfolio has position broker doesn't know about
   - `test_empty_portfolio` — no positions, both sides empty
   - `test_multiple_drifts_collected` — multiple instruments with differences

**Important notes:**
- Use `Money.amount` which is a `String` — parse with `.parse::<i64>()` and handle errors with `unwrap_or(0)`
- Portfolios use `HashMap<String, Position>` — iterate with `.values()` or `.iter()`
- For the BrokerPosition, accept strings for flexibility: side is "LONG"/"SHORT"/"FLAT"

**TDD required.**

**Existing types to use:**
- `crate::portfolio::PortfolioEngine` — has `positions: HashMap<String, Position>`, `cash_balance: Money`, `base_currency: String`
- `crate::portfolio::Position` — has `instrument_id: String`, `side: PositionSide` (Flat/Long/Short), `quantity: u64`, `cost_basis: Money`
- `crate::portfolio::PortfolioSnapshot` — already exists
- `crate::types::Money` — has `amount: String`, `currency: String`

**Register** in `core/src/lib.rs`:
- `pub mod reconciliation;`
- Add: `ReconciliationEngine`, `ReconciliationConfig`, `ReconciliationResult`, `ReconciliationDriftSeverity`, `PositionDrift`, `BrokerPosition`
