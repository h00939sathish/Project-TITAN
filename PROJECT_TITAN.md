# Project TITAN: Vision and Operating Model

> **Owner:** Product and Architecture Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council
> **Depends On:** [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md), [ROADMAP.md](ROADMAP.md)
> **Supersedes:** None
> **Review Frequency:** Annual; per material strategy change

## Identity

TITAN is an institutional autonomous quantitative research and trading operating system. It turns evidence into research candidates, candidates into reproducibly validated strategies, and approved strategies into tightly controlled paper or live operations. It is explicitly not an AI agent with broker credentials.

## Why this exists

The comparative R&D found no repository that should be adopted wholesale. NautilusTrader supplies the strongest execution foundation; Jesse supplies mature research/validation primitives; LLM_trader supplies bounded reflection concepts; Fincept supplies broker-connector lessons; new trade supplies useful but independently re-validated risk and event-store ideas. The analysis also identified dangerous gaps: LLM risk control, unwired circuit breakers, auto-reset kill switches, singletons as critical state, and un-reconciled execution. [Evidence: `../BEST_OF_BREED_MATRIX.md`, `../HOSTILE_REVIEW.md`, `../FAILURE_ANALYSIS.md`]

## Objectives

1. Autonomous, evidence-cited market and repository research.
2. Structured hypothesis and strategy-candidate generation.
3. Deterministic backtest, walk-forward, Monte Carlo, replay, and paper-trading validation.
4. Human-approved, risk-gated live deployment with reconciliation.
5. Continuous improvement based on production facts, never autonomous capital-policy changes.

## System boundaries

| Domain | Responsibility | Authority |
|---|---|---|
| Research and AI | knowledge retrieval, hypothesis generation, falsification, reflection | advisory only |
| Validation | datasets, simulations, statistical challenge, promotion evidence | may reject; cannot trade |
| Strategy | transform market events into intents | cannot create orders directly |
| Risk and portfolio | deterministic limits, sizing, exposure, capital allocation | veto authority |
| Execution | order lifecycle, broker adapters, idempotency, reconciliation | acts only on approved intents |
| Operations | configuration, observability, incidents, deployment | controls environment, audited |

## Architecture philosophy

TITAN is a modular event-driven core with explicit state and durable facts. It may begin as a well-bounded deployable rather than premature microservices; process boundaries are introduced only when isolation, latency, scale, or ownership evidence justifies them. The event log supports audit and recovery but does not justify speculative CQRS projections. See `ARCHITECTURE.md` and `ADR.md`.

## Long-term vision and phases

**Foundation:** deterministic core, data contracts, test harness, observability, simulation, and paper trading. **Controlled operation:** limited instruments/brokers, reconciliation and human live approval. **Scale:** multi-asset and multi-broker only after capacity and failure evidence. **Learning:** advisory knowledge and reflection improve research under governance. Roadmap gates are defined in `ROADMAP.md`; the original staged analysis is `../IMPLEMENTATION_ROADMAP.md`.

## Engineering culture

Disagree with evidence, make uncertainty visible, and prefer deletion to accidental complexity. Every production feature has an owner, runbook, metrics, failure test, rollback procedure, and retirement trigger. Risk can halt delivery; no commercial deadline overrides safety.

## Definition of success

TITAN is successful when a senior engineer can trace every live action from source event through deterministic risk decision and broker acknowledgement; reproduce its validation; detect and reconcile divergence; halt safely; and understand why each subsystem exists without reading original repositories.
