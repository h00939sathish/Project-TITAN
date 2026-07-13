# Task F2: Conduct Operational Readiness Review

## Goal

Walk through every item in `specifications/ORR-checklist.md`, verify or waive each, and produce a signed assessment document at `knowledge/benchmarks/orr-phase-f-assessment.md`.

## Files to create

- `knowledge/benchmarks/orr-phase-f-assessment.md` — the ORR assessment document

## Structure of the assessment document

### 1. Architecture

For each item in ORR-checklist.md Architecture section:
- Read each spec file in `specifications/` (there are 8+ .spec.md files plus cross-cutting specs)
- Verify each subsystem boundary is documented
- Verify the event store is canonical source (check core/src/event_store.rs)
- Check for disposable caches

### 2. Performance

Note all budgets from PERFORMANCE_SPEC.md. Since no benchmarks have been recorded in `knowledge/benchmarks/`, every item will be marked as "Not yet measured — deferred to post-Phase-F optimization cycle."

### 3. Risk controls

Check the following against the codebase:
- Is risk gate the sole path? (check core/src/risk.rs, check that only RiskGate::evaluate creates ApprovedOrderIntent)
- Are all 9 risk checks from Risk.spec.md implemented and tested? (check core/src/risk.rs tests)
- Does kill switch persist across restarts? (check current implementation — currently in-memory only)
- Has kill switch been tested end-to-end? (check tests/integration/test_paper_vertical_slice.py)
- Is manual release procedure documented? (check docs/runbooks/paper-session.md)

### 4. Monitoring and alerting

Evaluate the telemetry module created in F1:
- structured logs with correlation_id
- Metrics emitted for risk, kill-switch, drift, event lag
- Safety alerts
- Dashboard existence

### 5. Recovery

Evaluate:
- Restart procedure (load from event store, reconcile)
- Event store loss recovery
- Broker disconnect procedure  
- Reconciliation drift handling (check Rust implementation)
- Chaos tests

### 6. Testing

- Check FAILURE_MATRIX.md rows against existing tests
  - Broker disconnect: tests/integration/test_paper_vertical_slice.py has some coverage
  - Broker timeout: simulated adapter in tests/adapters/
  - Duplicate fill: not directly tested
  - Event store write failure: not tested
  - Event store corruption: not tested
  - Reconciliation drift: core/src/reconciliation.rs has tests
  - Kill switch: core/src/risk.rs has tests
  - Configuration load failure: not tested
- Count unit tests (62 Rust + Python)
- Count integration tests
- Count replay tests

### 7. Security

All items: no credentials in source. (This is paper-only.)

### 8. Runbooks

Check docs/runbooks/paper-session.md and docs/runbooks/incident.md exist and cover required items.

### 9. Rust/Python boundary evaluation

Evaluate each subsystem:
- Risk (Rust core + Python CLI wrappers) — good boundary?
- Portfolio (Rust core) — good?
- Reconciliation (Rust core) — good?
- Orders/state machines (Rust core) — good?
- Event store (Rust core, Python tests) — good?
- Strategy (Python) — good?
- Data pipeline (Python) — good?
- Backtest (Python) — good?
- Telemetry (Python, F1) — good?

Identify any code paths that should move:
- Python to Rust: event store scanning for replay could be faster in Rust
- Rust to Python: none identified

### 10. Optimization priority list

Based on gaps found, priority-order the optimizations:
1. Benchmark harness — establish baseline measurements
2. Performance benchmarks for key budgets
3. Event store persistence for kill switch state
4. Structured logging wired into runtime
5. Metrics emission wired into runtime

### 11. Sign-off

Include sign-off section:
- **Architecture Council representative:** (self-review: [name])
- **Risk Owner:** (self-review: [name])
- **Developer (self-review):** TITAN Development

**Date:** 2026-07-13
**Result:** Conditional (list conditions)

## Conditions for this phase

Document which ORR items are NOT yet met and are waived for this phase. Key conditions:
1. Performance benchmarks not yet measured — deferred to post-Phase-F optimization
2. Kill-switch state persistence is in-memory only — acceptable for paper
3. No live dashboards or alerting infrastructure — acceptable for paper
4. FAILURE_MATRIX coverage is partial — remaining rows noted for future phases

## Acceptance criteria

- Document exists at `knowledge/benchmarks/orr-phase-f-assessment.md`
- Every ORR-checklist.md item has a clear verdict: ✅ Verified, ⚠️ Partial, ❌ Missing
- Rust/Python boundary is evaluated
- Optimization priority list exists
- Sign-off section is filled

## Constraints

- No code changes — this is purely a documentation/assessment task
- Be honest about gaps — this is a paper-only assessment, not a live trading sign-off
- Follow the same format as existing knowledge/ documents
