# Deployment and Resilience

> **Owner:** Platform Operations
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Release Owner; Risk Owner for live promotion
> **Depends On:** [IMPLEMENTATION_PLAYBOOK.md](IMPLEMENTATION_PLAYBOOK.md), [OBSERVABILITY.md](OBSERVABILITY.md), [SECURITY.md](SECURITY.md)
> **Supersedes:** None
> **Review Frequency:** Per environment/recovery change; quarterly otherwise

## Environments

| Environment | Purpose | Broker/capital authority |
|---|---|---|
| Local | deterministic development and fixtures | none |
| Simulation | replay/backtest/load/chaos validation | simulated only |
| Paper | real external connectivity and operational rehearsal | no capital |
| Staging | production-like release/configuration verification | isolated/non-economic capability |
| Production | approved controlled operation | human-authorized, risk-gated only |

Environments have separate identities, secrets, network boundaries, data classifications, and immutable configuration. Promotion moves the same signed artifact and declared strategy/configuration package; it never rebuilds or manually patches between stages.

## Release and rollback

Release evidence includes artifact/SBOM/provenance, migrations, contract compatibility, test/replay/performance results, dashboards/alerts, risk approval, runbook, and rollback plan. Deploy with health checks and routing disabled; restore state, validate dependencies, reconcile brokers, and enable only through approved state transition. Rollback stops new intent admission, preserves event/audit history, cancels or reduces orders under [RISK_POLICY.md](RISK_POLICY.md), restores compatible artifact/configuration, then reconciles before reactivation. Database/event migrations require tested forward and backward/compensating recovery paths.

## Disaster recovery

Define and test recovery objectives per data class: event/audit facts require durable replicated recovery; projections rebuild from events; raw/normalized data restores from immutable lake copies; caches and vector stores are recreatable. A regional/service loss fails trading closed, establishes broker truth, and resumes only after data-store integrity, configuration, adapter health, and reconciliation evidence are approved. Conduct at least quarterly restore and broker-disconnect drills; record objective, measured recovery, gaps, and corrective actions.

## Operational ownership

Every deployment has accountable release, risk, and on-call owners; release digest; approved change record; live limits; dashboard/runbook links; and scheduled post-deploy review. Observe SLOs and control health under [OBSERVABILITY.md](OBSERVABILITY.md). The staged deployment posture applies the reliability and failure evidence in `../RELIABILITY_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

