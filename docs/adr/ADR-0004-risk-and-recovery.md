# ADR-0004: Risk, halt, recovery, and reconciliation invariants

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Chief Risk Office, Architecture Council
- **Decision scope:** Risk gate, kill switch, trading state, reconciliation
- **Supersedes / superseded by:** None

## Context

The R&D risk-engine comparison identifies non-negotiable safety invariants: deterministic risk gate, persistent fail-closed kill switch, `ACTIVE`/`REDUCING`/`HALTED` states, and reconciliation at every state transition. These must be wired into the production path, not declared as separate modules.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §5: NautilusTrader's typed denial reasons and state machines are the strongest reference; new trade's kill-switch concept is useful but its auto-reset and race-condition defects are rejected.
- `../RISK_ENGINE_COMPARISON.md`: LLM risk debate is prohibited; pre-trade and portfolio risk must be deterministic.
- `../FAILURE_ANALYSIS.md`: critical safety mechanisms are unwired across all evaluated repositories.

## Decision

1. **Risk gate is the sole path from TradeIntent to ApprovedOrderIntent.** No strategy, AI agent, or operator shortcut may bypass it. Every rejection is persisted with reason codes and rule versions.
2. **Kill switch is persistent, fail-closed, and manually released.** Stored in SQLite (same as event store). On unreadable state, the system starts in HALTED. Release requires operator action (audited CLI or API call) after reconciliation.
3. **Trading states** — `ACTIVE` (normal), `REDUCING` (reduction-only intents), `HALTED` (no intents). Transitions are persisted events.
4. **Reconciliation runs at startup, periodically, after disconnect, before/after halt release, and on ambiguous order state.** Critical drift (beyond configured threshold) halts routing. Warning drift alerts.
5. **Risk gate pipeline** — schema → eligibility → freshness → limits → position → drawdown → liquidity → broker health. Each check is typed, versioned, and independently testable.

## Alternatives and trade-offs

- **Auto-reset kill switch** — convenient but creates a race window where a recurring fault re-triggers a halt immediately after automated release. Rejected per `../FAILURE_ANALYSIS.md`.
- **LLM confidence as a risk input** — would add non-deterministic reasoning to the capital path. Rejected per `../AI_AGENT_COMPARISON.md`.
- **Manual-only reconciliation** — must be automated to detect drift before it becomes critical.

## Consequences

- Risk gate latency is on the hot path (intent → execution). Latency budget in PERFORMANCE_SPEC.md (<50 μs per check) keeps the overhead manageable.
- Kill-switch state persistence means restart behavior is always HALTED if the DB is unavailable. This is a safety feature, not a bug.

## Validation and operations

- Every risk check has a unit test.
- Kill switch has an end-to-end test: trigger during active order lifecycle, verify no new orders, verify cancel, verify HALTED, verify manual release.
- Reconciliation drift (critical) has a chaos test: inject divergence, verify halt, verify alert.
- See ORR-checklist.md for the full review.

## Approval

Chief Risk Office — 2026-07-13
