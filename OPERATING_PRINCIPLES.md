# Project TITAN Operating Principles

> **Owner:** Architecture Council
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council and Risk Owner
> **Depends On:** R&D evidence base
> **Supersedes:** None
> **Review Frequency:** Annual; on a material governance change

## Purpose

TITAN is an institutional autonomous quantitative research and trading operating system, not an AI trading bot. These principles govern every design, experiment, change, and production decision. They interpret the R&D record in `../EXECUTIVE_SUMMARY.md`, `../IDEAL_PLATFORM.md`, and `../ADOPTION_DECISIONS.md`.

## Non-negotiable principles

1. **Evidence over opinion.** A proposal states its source evidence, counter-evidence, measurable acceptance criteria, and retirement condition. Popularity and novelty are not evidence.
2. **Reliability over novelty.** A feature that cannot recover, reconcile, observe, and be tested is incomplete. This addresses the recurring “exists but is not wired” failure mode documented in `../FAILURE_ANALYSIS.md`.
3. **AI proposes; deterministic systems decide.** AI may research, summarize, hypothesize, retrieve experience, or draft. Deterministic, audited code validates risk, controls portfolio state, and authorizes orders.
4. **Capital is never delegated to a model.** No prompt, agent output, or AI confidence score may place, approve, resize, cancel, or bypass the deterministic order-and-risk path.
5. **Every subsystem earns its existence.** Prefer the smallest composable mechanism that satisfies a proven requirement. Remove unused dependencies, duplicated state, and dormant safety features.
6. **Measure before optimizing.** Establish a workload, baseline, p95/p99 latency, throughput, allocation and failure budget before changing performance-sensitive code. See `../PERFORMANCE_COMPARISON.md`.
7. **One source of truth for material state.** Orders, fills, positions, balances, risk limits, and kill-switch state are durable facts with explicit ownership; caches are reconstructible views.
8. **Architecture follows evidence.** Adopt patterns, not repositories: typed eventing and reconciliation from NautilusTrader; validation and research techniques from Jesse; advisory reflection from LLM_trader; broker connectors from Fincept; selected risk concepts from new trade. See `../BEST_OF_BREED_MATRIX.md`.
9. **Institutional thinking over hobby-project convenience.** Reconciliation, idempotency, staged release, rollback, least privilege, and auditability are first-class requirements.
10. **Simplicity is a safety control.** No distributed service, CQRS projection, agent, model, or dependency is introduced without a documented operational advantage and owner.

## The four continuous loops

| Loop | Permanent cycle | Required output |
|---|---|---|
| Research | observe → source → challenge → experiment → retain | evidence record and reproducible result |
| Architecture | measure → review complexity/reliability → decide → retire | ADR or explicit no-change decision |
| Implementation | design → test → review → paper trade → release | tested, observable, reversible increment |
| Evolution | collect production facts → reconcile → reflect → improve | ranked improvement hypothesis; no autonomous capital change |

## Decision test

Before approval, answer: Why now? Why this design? Which alternatives were rejected? What evidence supports it? What fails first? How is it tested, observed, rolled back, and retired? If an answer is unknown, the work remains research.

## Authority order

`AGENTS.md` is the operating constitution. `RISK_POLICY.md` overrides convenience and delivery pressure. `ARCHITECTURE.md`, active ADRs, and approved configuration define the technical contract. Evidence reports are architectural inputs and must be revised only through the research and ADR process.
