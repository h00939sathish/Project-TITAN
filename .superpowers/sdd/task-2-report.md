# Task F2: Operational Readiness Review — Report

**Status:** DONE_WITH_CONCERNS

## Summary

Completed ORR Phase F assessment at `knowledge/benchmarks/orr-phase-f-assessment.md`. 
32 ORR checklist items evaluated: 10 ✅ Verified, 7 ⚠️ Partial, 15 ❌ Missing 
(with waivers for performance/security paper-phase items).

## Key findings

- **Architecture:** All 8 subsystem boundaries documented and matching implementation. Clean dependency graph.
- **Risk controls:** RiskGate is sole path ✅. 9 checks implemented (8 of 9 tested — market-data freshness not wired). Kill switch tested end-to-end ✅ but in-memory only ❌.
- **Monitoring/alerting:** Not implemented. Telemetry module exists but is unwired. Acceptable for paper.
- **Recovery:** Reconciliation drift detection implemented ✅. Restart-from-event-store ❌, backup/restore ❌, broker disconnect automation ⚠️.
- **Testing:** 208 total tests (62 Rust + 118 Python + 28 integration/replay/adapter). State machine coverage excellent ✅. FAILURE_MATRIX coverage 3/14 rows ❌.
- **Security:** Clean (no credentials). All paper-deferred items waived.
- **Performance:** 0/12 budgets measured. Benchmark harness deferred to post-Phase-F.

## Commits

- `a7e3b7f` — feat: ORR Phase F assessment document

## Concerns

1. Market-data freshness check is defined in spec and ReasonCode exists but is never called — this is a spec/implementation gap.
2. Kill switch defaults to ARMED (not HALTED) on restart, violating the "fail closed on unreadable state" invariant.
3. 7 of 14 FAILURE_MATRIX rows have no tests — these represent real failure modes that cannot be validated.
4. Telemetry/HealthReporter exists but is completely unwired from runtime — it's dead code.
5. No restart-from-event-store procedure exists — the event store can replay state but nothing orchestrates this.

## Files

- `knowledge/benchmarks/orr-phase-f-assessment.md` — Assessment document
- `specifications/ORR-checklist.md` — Source checklist evaluated
