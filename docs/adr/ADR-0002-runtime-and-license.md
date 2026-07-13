# ADR-0002: Runtime architecture and license posture

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Architecture Council
- **Decision scope:** All code — execution core, Python platform layer, dependencies
- **Supersedes / superseded by:** None

## Context

The R&D evidence identifies NautilusTrader as the strongest execution reference but its LGPL license and dual-stack (Rust + Python) complexity require careful evaluation. The selected runtime architecture must balance performance, safety, solo-developer productivity, and licensing certainty.

## Evidence

- `../ADOPTION_DECISIONS.md`: NautilusTrader patterns (typed messages, state machines, reconciliation) are adopted; its code is not.
- `../ARCHITECTURE_COMPARISON.md`: typed event-driven microkernel is the target pattern.
- `../PERFORMANCE_COMPARISON.md`: Rust hot-path yields 10-100x latency improvement over Python for state-machine and serialization work.
- `../FINCEPT_DELTA_REPORT.md`: demonstrates why assuming upstream compatibility and license posture is dangerous.
- `EVIDENCE_SYNTHESIS.md`: confirms clean-room adoption of patterns, not copying code.

## Decision

1. **Rust + Python via PyO3/maturin.** Rust owns the deterministic execution core: domain types, event store, order state machine, risk gate, kill switch, portfolio projection, reconciliation engine, broker adapter trait. Python owns strategy logic, data orchestration, CLI, backtest configuration, and test harnesses.
2. **Clean-room implementation.** No NautilusTrader, Jesse, Fincept, new trade, or TRADE source code is copied. Patterns and interfaces are independently reimplemented. Every dependency (Rust crate, Python package) is reviewed for license compatibility and pinned at a specific version.
3. **Single-process deployment.** Rust and Python share a single process via native Python extensions. This eliminates IPC complexity, simplifies deployment, and preserves the solo-developer advantage.
4. **License posture.** All direct dependencies must be MIT, Apache 2.0, BSD, or similarly permissive. LGPL dependencies require legal review and, if accepted, dynamic linking only. No GPL dependencies.

## Alternatives and trade-offs

- **Pure Python** — faster initial velocity but risks hitting performance walls. The PERFORMANCE_SPEC.md budgets are achievable in Python with careful optimization but leave no headroom. Rejected because Rust-from-day-one avoids a painful rewrite.
- **Separate Rust binary + Python IPC** — cleaner language boundary but adds deployment complexity, serialization overhead, and operational burden. Rejected for solo-developer pragmatism.
- **Adopt NautilusTrader directly** — would accelerate initial core but introduces LGPL obligations, dual-stack complexity, and inherited architectural constraints. Rejected per ADOPTION_DECISIONS.md.

## Consequences

- Rust development is slower than Python for initial type/system design. The PLAN.md estimate accounts for this.
- PyO3 FFI boundary requires careful design to avoid copy overhead on the hot path.
- Solo developer must be proficient in both Rust and Python.

## Validation and operations

- Performance budgets in PERFORMANCE_SPEC.md are verified during each implementation phase.
- If a profile shows a module on the wrong side of the Rust/Python boundary, ADR-0002 is revisited via a new ADR.
- Rollback: if the Rust/Python split proves unproductive, an ADR can move components to pure Python.

## Approval

Architecture Council — 2026-07-13
