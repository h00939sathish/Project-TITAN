# Task 2 Report: Fail closed when boot reconciliation cannot fetch truth

## Summary

Boot reconciliation now detects when broker snapshot fetches raise exceptions,
returning a `snapshot_fetch_failed=True` dict and halting the system via
`transition_on_boot` instead of silently swallowing the error and proceeding.

## Changes

### `src/titan/recovery/restart.py`

- `reconcile_on_boot`: track `snapshot_fetch_failed` across both snapshot
  fetches (positions, holdings). If either raises, return an early result with
  `snapshot_fetch_failed=True`, `reconciled=False`, and a placeholder drift
  detail string.
- `transition_on_boot`: check `snapshot_fetch_failed` (via `.get()` for
  backward compat) before the drift check; set `TradingState.Halted` and
  return `"HALTED (broker truth unavailable)"`.

### `tests/recovery/test_restart.py`

- Added `SnapshotFailureAdapter` class at module level (raises `RuntimeError`
  on both `positions()` and `holdings()`).
- Added `test_boot_stays_halted_when_broker_truth_is_unavailable` as a method
  of `TestRecoverFromEventStore`.

## Verification

- `python -m pytest tests/recovery/test_restart.py::TestRecoverFromEventStore::test_boot_stays_halted_when_broker_truth_is_unavailable`
  — FAIL (red) before fix, PASS after.
- `python -m pytest tests/recovery/test_restart.py tests/adapters/test_simulated_adapter_contract.py`
  — 18 passed, confirming no regressions.

## Commit

```
74aad1e fix: halt recovery when broker truth is unavailable
```

## Files modified

- `src/titan/recovery/restart.py`
- `tests/recovery/test_restart.py`
