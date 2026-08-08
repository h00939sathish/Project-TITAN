# Project TITAN Roadmap

> **Owner:** Product and Architecture Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council and Risk Owner
> **Depends On:** [PROJECT_TITAN.md](PROJECT_TITAN.md), [IMPLEMENTATION_PLAYBOOK.md](IMPLEMENTATION_PLAYBOOK.md)
> **Supersedes:** None
> **Review Frequency:** Monthly; at every phase-gate decision

## Governing rule

Time horizons are planning aids, not delivery promises. A phase opens only when its predecessor’s evidence and risk gates are satisfied. This refines the source roadmap using the corrective findings in `../HOSTILE_REVIEW.md` and `../FINCEPT_DELTA_REPORT.md`.

| Phase | Outcome | Entry / exit gate |
|---|---|---|
| 0 — Evidence foundation | source catalog, ADR process, contracts, threat/risk model | evidence reports reconciled; authority documents approved |
| 1 — Deterministic core | typed event kernel, event store, state machines, test/replay harness | restart and duplicate-delivery tests; no ambiguous state owner |
| 2 — Risk and execution | pre-trade gate, persistent kill switch, portfolio limits, adapter contract, reconciliation | kill-switch/reconciliation chaos tests; paper broker integration |
| 3 — Research and validation | data-quality pipeline, indicators, backtest, WFO, Monte Carlo, experiment records | reproducible strategy package and falsification evidence |
| 4 — Paper operation | limited instruments/broker, runbooks, monitoring, incident drill | sustained paper reconciliation and operational readiness review |
| 5 — Restricted live | human-approved bounded allocation | dual approval, rollback drill, risk limits, on-call coverage |
| 6 — Scale and evolution | additional assets/brokers and advisory learning | capacity, reliability, liquidity and governance evidence per expansion |

## Near-term priorities

1. Validate upstream versions and license boundaries before adopting any implementation; the Fincept delta report demonstrates why local assumptions expire.
2. Build contracts and replay fixtures before adapters or strategies.
3. Make kill switch, reconciliation, idempotency, and observability end-to-end—not dormant modules.
4. Establish paper-trading and incident rehearsal before pursuing autonomous research breadth.

## Technical-debt and research backlog

Continuously retire unused dependencies, duplicated orchestration, implicit state, unversioned configuration, and broad exception handling. Research backlog: market-data quality contracts, impact/correlation model calibration, multi-asset state partitioning, capacity baselines, broker failover, experiment lineage, and advisory-memory retrieval quality. Each backlog item needs an owner, evidence question, expected value, and retirement trigger.

## Production milestones

No milestone is marked complete by code merge. A production milestone requires artifact provenance, measured SLOs, test/paper evidence, reconciliation results, risk sign-off, a tested rollback, current documentation, and an accountable operator. Current status starts at Phase 0 until those artifacts are recorded.
