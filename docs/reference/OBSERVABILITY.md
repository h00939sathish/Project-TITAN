# Observability

> **Owner:** Reliability Engineering
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Reliability Owner; Risk Owner for trading safety alerts
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md), [RISK_POLICY.md](RISK_POLICY.md)
> **Supersedes:** None
> **Review Frequency:** Per production incident; quarterly otherwise

## Objective

Operators must be able to answer what happened, where, why, how much it affects, and what safe action to take—without reconstructing truth from scattered logs. Observability is part of the execution path design, responding to the operational gaps catalogued in `../RELIABILITY_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

## Telemetry contract

Structured logs, metrics, and traces carry `service`, `environment`, release/config/strategy digests, `correlation_id`, `causation_id`, `account_scope` (masked), and message/order ids where permitted. Logs record state transitions and decision reasons; metrics measure rates, latency, saturation, and outcomes; traces connect ingress through risk, execution, adapter, persistence, and reconciliation. Never emit secrets, raw credentials, or sensitive prompt content.

## Required signals and dashboards

| Domain | Signals | Dashboard question |
|---|---|---|
| Market data | age, gaps, invalid records, ingest lag | Is input current and trustworthy? |
| Risk | decision latency, reject/breach reason, limit headroom, halt state | Is deterministic protection working? |
| Execution | intent-to-ack/fill p50/p95/p99, unknown orders, retry/error rate, open orders | Are orders progressing safely? |
| Broker | connectivity, auth refresh, API/rate-limit errors, snapshot lag | Can the adapter establish truth? |
| Reconciliation | drift count/value/age, completion duration | Do internal and broker records agree? |
| Platform | event lag, store failures, queue depth, CPU/memory, deployment version | Can the platform operate within capacity? |
| AI | tool denials, schema failure, source coverage, cost/latency | Is advisory automation bounded? |

## SLOs and alert policy

Each production service publishes availability, latency, correctness, and freshness SLOs with an owner, measurement window, error budget, and safe degradation. Safety alerts page immediately for kill-switch changes, material reconciliation drift, risk-gate unavailability, stale critical data while active, ambiguous order growth, unauthorized tool attempt, or audit-store failure. Capacity and quality alerts create tickets before the error budget is exhausted. Alerts name impact, current state, correlation/runbook link, owner, and first containment action; alert volume is reviewed for actionability.

## Incident response

Detect → classify → contain → preserve evidence → reconcile → communicate → recover → learn. When economic truth is uncertain, halt new routing and follow [RISK_POLICY.md](RISK_POLICY.md). The incident record includes timeline, affected scope, configuration/release digests, decisions, broker snapshots, mitigations, owner, root cause, and corrective actions. A severity-one/two incident updates the relevant runbook, test, dashboard/alert, ADR, and handbook document before closure.

## Retention and review

Retain audit and decision telemetry with the corresponding event-retention policy; aggregate high-volume metrics after their diagnostic window; protect trace/log access through `SECURITY.md`. Conduct weekly operational review of alerts/SLOs and quarterly dashboard/runbook drills, including a broker disconnect and reconciliation discrepancy.

