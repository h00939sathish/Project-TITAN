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
- Recovery: ⚠️ State persistence across restarts is deferred
- Gaps: Event store corruption detection, state persistence, fail-halted on unreadable store
