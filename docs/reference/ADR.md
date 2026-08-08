# Architecture Decision Records

> **Owner:** Architecture Council
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council
> **Depends On:** [GOVERNANCE.md](GOVERNANCE.md)
> **Supersedes:** None
> **Review Frequency:** Per consequential decision; annual template review

## Policy

An ADR preserves why a consequential technical or operational choice was made at a point in time. It is required for changes to execution, risk, persistence, message contracts, broker boundaries, deployment topology, model authority, security boundaries, or any decision that creates long-lived coupling. See `GOVERNANCE.md`.

## Status values

`Proposed`, `Accepted`, `Rejected`, `Superseded`, and `Retired`. Accepted records are not rewritten; a later ADR supersedes them and links back.

## Required template

```markdown
# ADR-NNNN: <short imperative decision>

- Status: Proposed | Accepted | Rejected | Superseded | Retired
- Date: YYYY-MM-DD
- Owners: <accountable roles>
- Decision scope: <systems, environments, data>
- Supersedes / superseded by: <ADR links or none>

## Context
Problem, constraints, decision deadline, and affected invariants.

## Evidence
Links to source code, tests, benchmarks, incidents, experiments, and R&D reports.
State evidence grades and unresolved uncertainty.

## Decision
The exact decision, interfaces/versions, authority boundary, and default behavior.

## Alternatives and trade-offs
For each credible alternative: benefit, cost, failure mode, and reason rejected.

## Consequences
Performance, reliability, security, operations, migration, ownership, and debt.

## Validation and operations
Acceptance tests, metrics, alerts, rollback, recovery, and retirement trigger.

## Approval
Required reviewers, decision date, and any time-bounded exception.
```

## Example: enforce deterministic authorization

### ADR-0001: Route all executable intents through a deterministic risk gate

- **Status:** Accepted
- **Scope:** all paper and live strategy runtimes

**Context.** Research components may generate useful hypotheses but are nondeterministic and susceptible to untrusted input. Comparative analysis identifies LLM-as-risk-manager and unwired safety controls as unacceptable failure modes. [Evidence: `../AI_AGENT_COMPARISON.md`; `../FAILURE_ANALYSIS.md`]

**Decision.** Strategies emit typed `TradeIntent`; only the deterministic risk service may emit `ApprovedOrderIntent`; only the execution engine may invoke an adapter. Persist every decision and rule version.

**Alternatives.** Direct strategy-to-broker coupling is rejected because it bypasses a single audit and veto point. LLM confidence/debate as an approval input is rejected because it cannot establish deterministic capital authority.

**Validation and rollback.** Contract tests prove rejected intents never call adapters; replay proves a recorded decision; live anomalies halt routing and retain the event record. The decision is retired only through a superseding ADR with equal or stronger safety evidence.
