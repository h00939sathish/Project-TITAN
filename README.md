# Project TITAN

> **Owner:** Developer Experience
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council
> **Depends On:** All active handbook documents
> **Supersedes:** None
> **Review Frequency:** Per handbook or bootstrap change; quarterly otherwise

An institutional autonomous quantitative research and trading operating system. TITAN separates AI-assisted research from deterministic portfolio, risk, execution, accounting, and reconciliation. It is deliberately designed as a governed synthesis of R&D evidence—not a copy of any evaluated repository.

## Start here

1. Read [Operating Principles](OPERATING_PRINCIPLES.md) and the [Agent Constitution](AGENTS.md).
2. Understand the product boundary in [Project Vision](PROJECT_TITAN.md).
3. Read [Architecture](ARCHITECTURE.md) and [Risk Policy](RISK_POLICY.md) before any execution-affecting work.
4. Follow the [Implementation Playbook](IMPLEMENTATION_PLAYBOOK.md) and record material choices in [ADRs](ADR.md).

## Architecture in one sentence

Research and AI propose structured hypotheses; validation tests them; strategies emit typed intents; deterministic risk approves or rejects them; execution routes approved orders; a durable event log and reconciliation establish operational truth.

## Documentation map

| Document | Role |
|---|---|
| [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md) | philosophical and evidence-led foundation |
| [AGENTS.md](AGENTS.md) | mandatory rules for AI and contributors |
| [PROJECT_TITAN.md](PROJECT_TITAN.md) | vision, boundaries, and success definition |
| [ARCHITECTURE.md](ARCHITECTURE.md) | technical topology, flow, state, recovery |
| [GOVERNANCE.md](GOVERNANCE.md) | approvals, reviews, RFCs, and releases |
| [CODING_STANDARD.md](CODING_STANDARD.md) | implementation rules and anti-patterns |
| [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md) | evidence, experiments, and promotion |
| [TESTING_STANDARD.md](TESTING_STANDARD.md) | test layers and required invariants |
| [RISK_POLICY.md](RISK_POLICY.md) | limits, kill switch, and incident posture |
| [IMPLEMENTATION_PLAYBOOK.md](IMPLEMENTATION_PLAYBOOK.md) | lifecycle, gates, rollout, rollback |
| [ADR.md](ADR.md) | decision-record policy, template, and example |
| [ROADMAP.md](ROADMAP.md) | evidence-gated sequencing |
| [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md) | canonical messages, ownership, serialization, compatibility |
| [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) | data lake, stores, cache, lineage, retention |
| [AI_GOVERNANCE.md](AI_GOVERNANCE.md) | AI authority, tools, prompts, memory, evaluation |
| [EXECUTION_SPEC.md](EXECUTION_SPEC.md) | normative order lifecycle, timeout, retry, reconciliation |
| [OBSERVABILITY.md](OBSERVABILITY.md) | telemetry, SLOs, dashboards, alerts, incident practice |
| [SECURITY.md](SECURITY.md) | identity, secrets, encryption, RBAC, audit, sandboxing |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | intended module and repository boundaries |
| [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) | onboarding, boot, extension, test, and release workflow |
| [RESEARCH_ENGINE.md](RESEARCH_ENGINE.md) | hypothesis, factor, alpha, feature, experiment, promotion lifecycle |
| [STRATEGY_ENGINE.md](STRATEGY_ENGINE.md) | strategy packages, parameters, ensembles, activation, retirement |
| [BACKTEST_ENGINE.md](BACKTEST_ENGINE.md) | deterministic replay, fills, costs, latency, impact, corporate actions |
| [PORTFOLIO_ENGINE.md](PORTFOLIO_ENGINE.md) | accounts, valuation, allocation, PnL, margin, attribution |
| [BROKER_SPEC.md](BROKER_SPEC.md) | canonical broker interface, health, reconciliation, certification |
| [DATA_PIPELINE.md](DATA_PIPELINE.md) | ingestion, normalization, quality, publication, feature operations |
| [PLUGIN_SDK.md](PLUGIN_SDK.md) | secure extension contracts and plugin lifecycle |
| [DEPLOYMENT.md](DEPLOYMENT.md) | environments, release, rollback, disaster recovery |
| [EVIDENCE_SYNTHESIS.md](EVIDENCE_SYNTHESIS.md) | section-by-section R&D synthesis, conflicts, and pre-implementation ADR gates |
| [PLAN.md](PLAN.md) | evidence-gated solo-developer MVP implementation plan |
| [NEWPLAN.md](NEWPLAN.md) | post-MVP research, paper-operation, and restricted-live maturity plan |
| [docs/superpowers/plans/2026-07-13-cross-asset-validation.md](docs/superpowers/plans/2026-07-13-cross-asset-validation.md) | implementation plan for cross-asset validation reporting and gate coverage |

## Developer workflow

Identify evidence and subsystem ownership, design and document the boundary, write tests, implement a small reversible change, run the applicable test/replay/benchmark gates, then update documentation and ADRs. No change may cross into paper or live operation without the gates in `IMPLEMENTATION_PLAYBOOK.md` and `RISK_POLICY.md`.

## Research Progress

Experimental baselines against frozen synthetic fixtures. All results are OOS (2023-01-01 to 2024-12-31). See `knowledge/research/benchmarks/rejected-control-baselines.md` for full detail.

| Strategy | Instrument | Status | Sharpe | Win Rate | Trades |
|---|---|---|---|---|---|
| MA(5,20) | SPY | Rejected | 1.56 | 30.8% | 13 |
| MA(50,200) | SPY | Rejected | 0.00 | 0.0% | 0 |
| Mean Reversion | SPY | Rejected (gate) | 0.69 | 100.0% | 2 |
| Volatility Regime | SPY | Rejected (gate) | 1.36 | 76.9% | 26 |
| Volatility Regime | QQQ | Replicated | 0.63 | 64.9% | 37 |
| Volatility Regime | TLT | Rejected | -0.48 | 43.2% | 37 |
| Time-series Momentum | SPY | Accepted | 1.38 | 28.6% | 35 |
| Time-series Momentum | QQQ | Replicated | 0.87 | 34.0% | 47 |
| Volatility Regime (pooled) | SPY+QQQ | [pending] | - | - | - |

> Test count: `[verify count]`
>
> *See `knowledge/research/benchmarks/rejected-control-baselines.md` for full baseline detail, `knowledge/research/hypotheses/` for preregistrations, and `knowledge/research/experiments/` for frozen experiment records.*

## Evidence base

The source R&D reports live one directory above this suite: [repository catalog](../REPOSITORY_CATALOG.md), [architecture comparison](../ARCHITECTURE_COMPARISON.md), [performance comparison](../PERFORMANCE_COMPARISON.md), [reliability comparison](../RELIABILITY_COMPARISON.md), [risk-engine comparison](../RISK_ENGINE_COMPARISON.md), [strategy-engine comparison](../STRATEGY_ENGINE_COMPARISON.md), [AI-agent comparison](../AI_AGENT_COMPARISON.md), [best-of-breed matrix](../BEST_OF_BREED_MATRIX.md), [failure analysis](../FAILURE_ANALYSIS.md), [hostile review](../HOSTILE_REVIEW.md), [adoption decisions](../ADOPTION_DECISIONS.md), [ideal platform](../IDEAL_PLATFORM.md), [implementation roadmap](../IMPLEMENTATION_ROADMAP.md), [executive summary](../EXECUTIVE_SUMMARY.md), and [Fincept delta report](../FINCEPT_DELTA_REPORT.md). Every adoption is conditional on its evidence, license, maintained upstream status, and TITAN’s own validation.
