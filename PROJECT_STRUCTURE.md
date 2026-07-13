# Project Structure

> **Owner:** Core Platform Architecture
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council
> **Depends On:** [ARCHITECTURE.md](ARCHITECTURE.md), [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [CODING_STANDARD.md](CODING_STANDARD.md)
> **Supersedes:** None
> **Review Frequency:** Per new top-level boundary; quarterly otherwise

## Intended repository layout

```text
Project TITAN/
├── docs/                 # handbook, ADRs, RFCs, runbooks
├── contracts/            # canonical schemas, fixtures, compatibility tests
├── services/
│   ├── core/             # message routing, aggregate/state primitives
│   ├── risk/             # deterministic admission, limits, kill switch
│   ├── execution/        # order lifecycle, durable outbox, adapter orchestration
│   ├── portfolio/        # positions, PnL, exposure projections
│   ├── reconciliation/   # broker truth comparison and discrepancy workflow
│   ├── data/             # ingestion, normalization, quality gates
│   ├── research/         # experiments, datasets, validation orchestration
│   └── ai_advisory/      # bounded retrieval, hypothesis, reflection
├── adapters/             # broker, market-data, storage, provider boundaries
├── strategies/           # versioned strategy packages; no broker access
├── libraries/            # domain types, deterministic indicators, shared clients
├── infrastructure/       # environment definitions, deployment, policy-as-code
├── tests/                # unit, contract, integration, replay, chaos, performance
├── tools/                # developer automation; never production authority
└── artifacts/            # ignored/generated local artifacts; immutable artifacts external
```

## Boundary rules

`contracts/` has no service dependency and is imported by all producers/consumers. `libraries/` contains stable domain primitives, not service-specific behavior. `adapters/` depend inward on contracts but their SDK types never escape. `strategies/` can emit intents but cannot import execution/broker modules. `ai_advisory/` can create governed proposals only. Services communicate with typed contracts, not cross-service database access. Tests mirror the boundary and include contract fixtures as public API.

## Documentation and change placement

Keep ADRs under `docs/adr/`, RFCs under `docs/rfcs/`, runbooks under `docs/runbooks/`, and this handbook in the repository root until implementation chooses an approved documentation build structure. A feature changes its owning boundary plus contracts/tests/documents; it does not create a `common`, `utils`, or global state module to avoid a dependency decision. New top-level directories require an RFC/ADR.

## Bootstrap dependency order

Build contracts and domain types first; then event persistence/replay, risk and execution with a test adapter, portfolio/reconciliation, data/validation, and finally bounded AI advisory interfaces. This ordering prevents strategy, UI, or agent convenience from defining core economic semantics. [Evidence: `../IMPLEMENTATION_ROADMAP.md`; `../HOSTILE_REVIEW.md`]

