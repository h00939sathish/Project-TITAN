# Specifications

This directory contains the canonical specifications for every Project TITAN subsystem, cross-cutting concerns, and operational gates. Per ADR-0001, no implementation task opens until its specification is accepted.

## Template

Every `.spec.md` contains:

- **Purpose** — one-paragraph reason this subsystem exists
- **Boundary / Ownership** — what it owns, what it delegates
- **Inputs** — event/command types it consumes
- **Outputs** — event/command types it emits
- **Commands** — typed request messages it accepts
- **Events** — typed fact messages it emits
- **State machine** — Mermaid diagram of legal states and transitions
- **Dependencies** — which other subsystems it calls
- **Error taxonomy** — retryable, terminal, data-quality, risk, operational error classes
- **Metrics** — every metric name, type, and semantic meaning
- **Configuration** — every config key, type, default, and validation rule
- **Performance budget** — reference to PERFORMANCE_SPEC.md line item
- **Failure behavior** — reference to FAILURE_MATRIX.md line item

## Subsystem specs

| File | Subsystem | Implemented in |
|---|---|---|
| Money.spec.md | Decimal arithmetic, rounding, currency, precision | Phase B |
| Order.spec.md | Order state machine, lifecycle, idempotency | Phase B |
| Portfolio.spec.md | Positions, PnL, exposure, margin, valuation | Phase C |
| TradeIntent.spec.md | Intent schema, provenance, expiry | Phase B |
| Execution.spec.md | Order service, outbox, adapter contract | Phase C |
| Risk.spec.md | Risk gate pipeline, limits, kill switch | Phase C |
| StrategyRuntime.spec.md | Strategy warmup, signal deduplication, and intent proposal boundary | Phase J |
| Broker.spec.md | Session lifecycle, auth, reconciliation | Phase C/E |
| Replay.spec.md | Clock, determinism, fill models | Phase D |

## Cross-cutting specs

| File | Content |
|---|---|
| Governance.spec.md | Research → Architecture → Implementation → Evolution continuous loop definitions, state machine, metrics, and configuration |
| PERFORMANCE_SPEC.md | p99 latency budgets per subsystem |
| FAILURE_MATRIX.md | Failure → behavior → recovery → verification |
| VERSIONING.md | Independent version policy for all artifacts |
| ORR-checklist.md | Operational Readiness Review gates |
| PAT-checklist.md | Production Acceptance Test gates |
| contracts/README.md | Cross-reference to machine schemas in contracts/ |

## Lifecycle

- Specs are written in Phase -1, before any code.
- A spec is updated only when a material design decision changes, and always with an accompanying ADR.
- Implementation tests reference the spec's state machine, error taxonomy, and failure behavior as the ground truth.
- If a spec and implementation diverge, the spec is wrong until proven otherwise.
