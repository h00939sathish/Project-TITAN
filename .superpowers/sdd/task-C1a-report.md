# Task C1a Report — Rust Risk Types

## What was implemented

**New file:** `core/src/risk.rs` — 4 types with PyO3 bindings, state machine logic, and 15 unit tests.

**Modified files:** `core/src/lib.rs` (module registration), `core/src/types.rs` (added `Display` for `Money`, fixed `__str__` to delegate to it).

### 1. `TradingState` enum
- Variants: `Active`, `Reducing`, `Halted` (Default: `Active`)
- Pure Rust `transition()` with valid transitions: `Active→Reducing`, `Active→Halted`, `Reducing→Halted`, `Halted→Active`, `Halted→Reducing`
- `accepts_intents()`: only `Active`
- `#[pymethods]`: `__str__`, `__repr__`, `is_active()` (delegates to `accepts_intents`)

### 2. `KillSwitchState` enum
- Variants: `Armed`, `Triggered`, `Releasing`, `Released` (Default: `Armed`)
- `transition()`: `Armed→Triggered`, `Triggered→Releasing`, `Releasing→Released`, `Releasing→Triggered`, `Released→Armed`
- `is_triggered()`, `blocks_routing()` (Triggered or Releasing)
- `#[pymethods]`: `__str__`, `__repr__`, `is_triggered`, `blocks_routing`

### 3. `RiskConfig` struct
- 8 fields with `#[pyo3(get, set)]`
- `#[new]` constructor accepting all 8 args
- `Default` impl with spec values (1M USD notional, 10k qty, 50k pos, 10M exposure, 0.10 drawdown, 50k daily loss, 5000ms freshness)

### 4. `RiskReasonCode` enum
- 12 variants matching the spec

### 5. `core/src/types.rs` — added `impl fmt::Display for Money`
Required because tests compare Money values via `.to_string()`. Updated `__str__` to delegate to `Display`.

---

## TDD Evidence

### RED phase — before implementation
```
$ cargo test
error[E0599]: `types::Money` doesn't implement `std::fmt::Display`
  --> src\risk.rs:299:43
...
error: could not compile `titan_core` (lib test) due to 4 previous errors
```

Root cause: `Money` had no `Display` impl, so `.to_string()` calls in tests failed at compile time. The `todo!()` stubs were never reached.

### GREEN phase — after full implementation
```
$ cargo test
test result: ok. 23 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

$ cargo clippy --all-targets
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 6.80s
```

---

## Files changed

| File | Change |
|---|---|
| `core/src/risk.rs` | **Created** — 381 lines: 4 types + 15 tests |
| `core/src/lib.rs` | Added `pub mod risk;` and 4 `m.add_class` calls |
| `core/src/types.rs` | Added `use std::fmt;`, `impl fmt::Display for Money`, updated `__str__` to `self.to_string()` |

---

## Test results

```
cargo test: 23 passed, 0 failed (15 risk + 8 orders)
cargo clippy --all-targets: 0 warnings, 0 errors
```

### Risk-specific tests (15):
- `test_trading_state_default_is_active` — default is Active
- `test_trading_state_active_accepts_intents` — only Active accepts
- `test_trading_state_valid_transitions` — all 5 valid paths
- `test_trading_state_illegal_transitions` — Reducing→Active, self-transitions rejected
- `test_trading_state_is_active` — pymethod delegates correctly
- `test_kill_switch_default_is_armed` — default is Armed
- `test_kill_switch_is_triggered` — only Triggered state
- `test_kill_switch_blocks_routing` — Triggered + Releasing block
- `test_kill_switch_state_machine` — full cycle Armed→Triggered→Releasing→Released→Armed
- `test_kill_switch_release_re_trigger` — Releasing→Triggered re-trigger
- `test_kill_switch_no_auto_reset` — Triggered→Armed illegal
- `test_kill_switch_illegal_self_transitions` — all 4 states reject self-transition
- `test_risk_config_defaults` — all 8 fields match spec
- `test_risk_config_custom` — constructor sets fields
- `test_risk_reason_code_variants` — all 12 variants exist

---

## Self-review findings

1. **`Money` was missing `Display`** — the task brief listed `Display` as already present, but the actual code only had `__str__` (a PyO3 method). Added `impl fmt::Display` and made `__str__` delegate to it. This is correct: Rust's `Display` enables `.to_string()` which tests need.

2. **`from_py_object` added to `#[pyclass]`** — PyO3 0.29 deprecates automatic `FromPyObject` derive for types implementing `Clone`. All existing types in the codebase use `from_py_object`, so I followed the same convention to suppress deprecation warnings.

---

## Issues or concerns

None. All tests pass, clippy is clean, all spec requirements are met.
