# Engineering Governance

> **Owner:** Engineering Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Engineering Leadership
> **Depends On:** [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md), [ADR.md](ADR.md)
> **Supersedes:** None
> **Review Frequency:** Quarterly; after a governance incident

## Purpose

Governance makes safe decisions repeatable. It applies to code, research, configuration, models, data, vendors, and operating procedures. `AGENTS.md` and `RISK_POLICY.md` are higher authority where they conflict.

## Decision and review model

| Change class | Minimum evidence | Approval |
|---|---|---|
| Documentation or non-runtime refactor | review, link check | code owner |
| Research or strategy candidate | reproducible experiment and falsification | research owner |
| Execution, portfolio, risk, broker, state | tests, replay, failure recovery, ADR | subsystem owner + risk owner |
| Live configuration or promotion | paper-trading evidence, reconciliation, rollback | operations + risk + accountable human |
| Kill-switch release | reconciliation evidence and incident review | two authorized humans |

## RFC and ADR process

An RFC is required before a cross-subsystem or externally observable change. It describes the problem, constraints, alternatives, ownership, migration, metrics, operational load, security, and rollback. An accepted consequential decision is recorded in `ADR.md` format. ADRs are immutable historical records; supersede rather than edit their decision. This implements the evidence-first process established in `OPERATING_PRINCIPLES.md` and responds to the architectural drift concerns in `../HOSTILE_REVIEW.md`.

## Code review

Reviewers verify correct boundary placement, typed contracts, idempotency, state ownership, test quality, observability, configuration safety, failure recovery, and documentation. A risk or execution review cannot be self-approved. “Works locally” is not evidence for a production path. Security-sensitive changes require least-privilege and secret-handling review.

## Quality gates and release

Every merge must pass formatting, static analysis, unit and integration tests, and documentation link validation. Execution-affecting releases additionally require deterministic replay, performance comparison against baseline, failure-injection tests, paper trading, reconciliation, an approved rollback, and dashboard/alert verification. Promote immutable artifacts through research → simulation → paper → restricted live; never patch production by hand.

## Versioning and change control

Version public message schemas, strategy packages, configuration, model prompts, and data contracts. Persist the version with every decision and event. Backward compatibility is deliberate: consumers support the stated window or migration is atomic and reversible. Configuration changes are reviewed, signed/audited, and treated as releases.

## Documentation governance

The document owner updates affected sections in the same change. Links point to actual evidence or ADRs. Claims about benchmark, production, or compliance status include date, environment, method, and artifact. Quarterly, audit owners, stale decisions, unused dependencies, retired controls, and links. See `RESEARCH_PROTOCOL.md` for evidence standards.
