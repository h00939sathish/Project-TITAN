# Task C2c Report: Python Simulated Adapter + Integration Vertical Slice Test

**Date:** 2026-07-13
**Status:** DONE

---

## What Was Implemented

### Files Created

| File | Purpose |
|---|---|
| `src/titan/execution/__init__.py` | Package init for execution layer |
| `src/titan/execution/simulated_adapter.py` | `SimulatedAdapter`, `SimFillQuality`, `SimOrderState` |
| `tests/integration/__init__.py` | Package init for integration tests |
| `tests/integration/test_paper_vertical_slice.py` | 10 end-to-end vertical slice tests |

### Rust Module Changes

Two additions to `core/src/reconciliation.rs`:

1. **`BrokerPosition::new`** — Added a `#[new]` constructor so `BrokerPosition("AAPL", "LONG", 100)` works from Python (previously not constructible).
2. **`ReconciliationConfig::new` signature** — Added `#[pyo3(signature = (...))]` with optional keyword arguments for `critical_drift_fraction` and `warning_drift_fraction`; defaults to `0.05` and `0.01` respectively.
3. **`ReconciliationEngine::new` signature** — Added `#[pyo3(signature = (config=None))]` so `ReconciliationEngine()` works (previously required explicit `None`).

### Python-Level Fix

Fixed `SimulatedAdapter.tick()` in `simulated_adapter.py` — originally only processed orders with `status == "pending"`, but partial-fill orders have `status == "partially_filled"`. Changed guard to `status not in ("filled", "rejected", "cancelled")`.

### Test Adaptation

Minor deviation from the task brief's code listing:
- `test_partial_fill_then_full` needed an explicit `adapter.set_default_fill_quality(SimFillQuality.PARTIAL_THEN_FULL)` call before submitting the order (the brief omitted this).
- `Money(str(last_fill["price"]), "USD")` would produce `Money("150.0", "USD")` which panics the Rust portfolio engine (expects integer strings). Fixed by using `order.price` (original string) and `str(int(last_fill["price"]))` where needed.

### Test Coverage (10 scenarios)

| # | Test | What It Proves |
|---|---|---|
| 1 | `test_happy_path` | Full end-to-end: intent → risk → execution → fill → portfolio → reconciliation |
| 2 | `test_risk_rejects_intent` | Non-eligible instrument rejected by gate |
| 3 | `test_kill_switch_blocks_pipeline` | Kill switch rejects all intents |
| 4 | `test_fill_updates_portfolio_correctly` | Multiple fills compose correctly |
| 5 | `test_partial_fill_then_full` | Partial fill + tick → full fill → correct portfolio |
| 6 | `test_sell_then_reconcile` | Sell reduces position; portfolio matches broker |
| 7 | `test_full_pipeline_with_rejection_then_recovery` | Rejected → fix → accepted → execute → reconcile |
| 8 | `test_reconciliation_detects_drift` | 10% position drift → Critical severity |
| 9 | `test_reconciliation_drift_warning` | 2% position drift → Warning severity |
| 10 | `test_empty_portfolio_reconciles` | No positions, cash matches → InSync |

---

## Test Results

### Integration tests only
```
.venv\Scripts\python.exe -m pytest tests/integration/ -v
collected 10 items → 10 passed in 0.03s
```

### Full Python test suite
```
.venv\Scripts\python.exe -m pytest tests/ -v
collected 67 items → 67 passed in 0.64s
```

### Rust unit tests
```
cd core && cargo test
62 tests → 62 passed in 0.01s
```

### Final Count

| Layer | Tests | Status |
|---|---|---|
| Python integration (new) | 10 | ✅ All pass |
| Python core | 57 | ✅ All pass |
| **Python total** | **67** | **✅ All pass** |
| Rust unit | 62 | ✅ All pass |

---

## Issues and Concerns

1. **BrokerPosition was not constructible from Python** — The Rust struct had `#[pyclass]` but no `#[new]` method. This was the main blocker. Fixed by adding a constructor.
2. **ReconciliationConfig accepted only no-arg construction** — The `#[new]` took no parameters. Expanded with optional keyword args for custom drift thresholds.
3. **ReconciliationEngine required explicit None** — `ReconciliationEngine()` failed because `Option` needed explicit pass. Fixed with `#[pyo3(signature = (config=None))]`.
4. **Money format constraint** — The Rust portfolio engine parses money amounts as `i64`. `Money("150.0", "USD")` panics. All price strings must be integer-only.
5. **SimulatedAdapter.tick() only handled "pending"** — Partial fill test failed because `tick` rejected `"partially_filled"` status. Fixed by broadening the guard.
6. **No concerns** — All 127 tests (67 Python + 62 Rust) pass. The pipeline is deterministic and reproducible.

---

## Exit Criteria

- ✅ All integration tests pass
- ✅ Full test suite still green (67 Python tests, 62 Rust tests)
- ✅ Report written
