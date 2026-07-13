# Task G1 Report: Kill-switch and Trading-state Persistence

**Status:** DONE

## Summary

Implemented kill-switch and trading-state persistence across Python process restarts via the event store. Kill-switch and trading state are serialized into `RiskStateSnapshot` events, appended to the `EventStore`, and restored on startup via `RiskGate::load_or_default()` (or `restore_state()` for existing gates). Defaults to HALTED / Triggered (fail-closed) when no persisted state exists.

## Files Changed

| File | Change |
|---|---|
| `core/src/messages.rs` | Added `RiskStateSnapshot` struct with `to_json()`, `from_json()`, `__str__`, `__repr__` |
| `core/src/risk.rs` | Added `persist_state()`, `restore_state()`, `load_or_default()` methods; exposed `accepts_intents()` to Python; added `RiskConfig.default()` static method; added 2 Rust tests |
| `core/src/lib.rs` | Exposed `RiskStateSnapshot` to Python |
| `tests/risk/test_state_persistence.py` | New file — 5 Python tests for persistence round-trip |

## Test Results

- **Rust:** `cargo test` — 64 passed ✅ (62 existing + 2 new: `test_persist_and_restore_state`, `test_restore_defaults_to_halted_when_no_state`)
- **Python persistence:** `pytest tests/risk/test_state_persistence.py -v` — 5 passed ✅
- **Full regression:** `pytest tests/ -v` — 123 passed ✅ (118 existing + 5 new; no regressions)

## Commits

- `76371ec` — G1: Add RiskStateSnapshot, persist/restore state, load_or_default, 64 Rust / 123 Python tests pass

## Deviations from Brief

1. **Rust test `test_persist_and_restore_state`**: Also calls `gate.set_trading_state(TradingState::Halted)` after `trigger_kill_switch()` so that both states are actually persisted as changed and the restored assertions pass. The brief's original test expected `Halted` trading state after restore but `trigger_kill_switch()` does not change trading state — only the kill switch.

2. **Python test `test_persisted_state_halts_routing`**: Same fix — added `gate.set_trading_state(TradingState::Halted)` so both kill-switch and trading-state routing blocks are verified after restore.

3. **Added `RiskConfig.default()` static method**: Required by Python tests which call `RiskConfig.default()` (per brief). This was not previously exposed to Python — `RiskConfig` only had `__new__` with positional args.

4. **Exposed `TradingState.accepts_intents()` to Python**: Required by Python tests (`assert not gate.trading_state.accepts_intents()`). Previously only exposed in Rust impl block.

## Concerns

- The `RiskStateSnapshot` uses `format!("{:?}", enum)` for serialization of enum variant names (e.g. `"Triggered"`, `"Halted"`). This works because `Debug` derives produce the variant name exactly. If variants are renamed, persisted snapshots would break on deserialization — acceptable for early stage, but a migration strategy should be documented before production.
