# Drill: State Store Loss

**Date:** 2026-07-13
**Type:** Scheduled drill
**Severity:** Critical (simulated)
**Duration:** 10 minutes

## Scenario

Simulate event store unavailability. Verify:
- System fails closed (rejects intents)
- Kill switch state defaults to halted on unreadable state
- Operator can assess and document the issue

## Steps performed

1. Attempted to read from a nonexistent event store path
2. Verified EventStore.new("nonexistent.db") creates a new store (SQLite behavior)
3. Documented that SQLite creates files on open — corruption detection is not yet implemented
4. Verified RiskGate starts in ACTIVE (in-memory, no persistence dependency)

## Results

- Detection: ⚠️ Partial — EventStore constructor succeeds for new paths
- Containment: ✅ RiskGate is independent of persistence (in-memory state)
- Recovery: ✅ Fixed 2026-07-14 — `transition_on_boot()` now detects empty store and forces HALTED
- Gaps: Event store corruption detection, state persistence

## Fix (2026-07-14)

**Problem:** `recover_from_event_store()` used `RiskGate.load_or_default()` which correctly returns Halted for an empty store, but `transition_on_boot()` then overrode it to Active when no drift was detected (empty portfolio + empty broker = match).

**Fix:** `recover_from_event_store()` now detects whether the store had prior state (`store.count() > 0`). `transition_on_boot()` accepts a `store_was_empty` flag and keeps the system HALTED when set, regardless of drift state.
