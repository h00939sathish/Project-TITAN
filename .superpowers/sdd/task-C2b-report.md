# Task C2b Report: Rust Reconciliation Engine

**Status:** DONE

## What Was Implemented

Created `core/src/reconciliation.rs` with the full reconciliation engine:

1. **`ReconciliationDriftSeverity`** enum — `InSync`, `Warning`, `Critical` with `#[pyclass(eq, eq_int)]`
2. **`PositionDrift`** struct — per-instrument drift with instrument_id, expected/actual side/quantity, quantity_drift
3. **`ReconciliationResult`** struct — severity, position_drifts, cash_expected/actual/drift, summary string
4. **`ReconciliationConfig`** struct — `critical_drift_fraction` (default 0.05), `warning_drift_fraction` (default 0.01)
5. **`ReconciliationEngine`** struct — `new(config: Option<ReconciliationConfig>)` and `compare(portfolio, broker_positions, broker_cash) -> ReconciliationResult`
6. **`BrokerPosition`** struct — instrument_id, side String, quantity i64

### Compare Logic
- Iterates portfolio positions, matches by instrument_id to broker positions
- Converts sides to signed quantities: LONG→+qty, SHORT→−qty, FLAT→0 (for both portfolio `PositionSide` and broker side strings)
- Unknown positions on either side produce drift entries (expected=FLAT/0 or actual=0)
- Cash drift computed as absolute difference between parsed amounts
- Severity escalates: any drift fraction > `critical_drift_fraction` → Critical; > `warning_drift_fraction` → Warning; else InSync

### Module Registration
- `core/src/lib.rs`: added `pub mod reconciliation;` and all 6 classes registered with PyO3

## TDD Evidence

### RED Phase
Stub implementation returned empty results. All 8 reconciliation tests failed:
- `test_in_sync` — expected 1 position drift, got 0
- `test_small_position_drift_warning` — expected Warning, got InSync
- `test_large_position_drift_critical` — expected Critical, got InSync
- `test_cash_drift_critical` — expected Critical, got InSync
- `test_broker_has_unknown_position` — expected Critical, got InSync
- `test_portfolio_has_unknown_position` — expected Critical, got InSync
- `test_empty_portfolio` — passed (stub default was InSync, which is correct)
- `test_multiple_drifts_collected` — expected Warning, got InSync

### GREEN Phase
After implementing full logic: 7/8 passed. One remaining failure:
- `test_multiple_drifts_collected` — got Critical instead of Warning because broker SHORT quantities were not negated

After adding `signed_broker()` helper to convert broker side strings to signed i64: all 8 tests pass.

## Files Changed
- `core/src/reconciliation.rs` — created (new file, ~310 lines)
- `core/src/lib.rs` — added module registration and 6 class registrations
- `.superpowers/sdd/task-C2b-report.md` — this file

## Test Results

### `cargo test` — 62 passed, 0 failed
All 8 reconciliation tests + 26 portfolio + 14 orders + 14 risk tests pass.

### `cargo clippy` — clean
No clippy-specific warnings. Only pre-existing PyO3 deprecation notices (6 warnings about `HasAutomaticFromPyObject`, originating from pyo3 crate, not our code).

### `python -m maturin develop` — successful
Built and installed `titan-0.1.0` wheel for CPython 3.14.

## Self-Review Findings

1. **Broker quantity sign handling**: Initial implementation treated broker quantities as raw i64 without considering the side string. Broker `SHORT 48` was compared as +48 vs portfolio's -50, giving drift 98 instead of 2. Fixed by adding `signed_broker()` helper that negates SHORT quantities.

2. **Cash drift severity edge case**: When both portfolio and broker cash are 0 (e.g., empty portfolio), `max_cash` defaults to 1 via `.max(1)`, avoiding division by zero. Drift fraction becomes 0.0 → InSync. This is correct.

3. **Unknown position handling**: Broker positions not in portfolio produce `expected_side: "FLAT"`, `expected_quantity: 0`, with drift = |actual_quantity|. Portfolio positions not known to broker produce `actual_side: "FLAT"`, `actual_quantity: 0`. This matches the spec.

## Concerns

None. Implementation is complete and all gates pass.
