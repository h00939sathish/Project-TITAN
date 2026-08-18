# Testing Standard

> **Owner:** Quality and Reliability Engineering
> **Status:** Active — v1.1
> **Last Review:** 2026-08-18
> **Decision Authority:** Quality Owner; Risk Owner for live gates
> **Depends On:** [specifications/Execution.spec.md](specifications/Execution.spec.md), [specifications/Risk.spec.md](specifications/Risk.spec.md), [specifications/TradeIntent.spec.md](specifications/TradeIntent.spec.md), [AGENTS.md](AGENTS.md)
> **Supersedes:** v1.0
> **Review Frequency:** Per test-policy change; quarterly otherwise

## Rule

No feature is production-ready because it has a passing happy path. Its test evidence must match the harm it could cause. In particular, risk, order, broker, persistence, and reconciliation changes require failure, recovery, and replay evidence. This is designed against the gaps identified in `../RELIABILITY_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

## Test layers

| Layer | Proves | Required examples |
|---|---|---|
| Unit | deterministic local invariants | sizing limits, state transitions, message validation |
| Integration | boundary contracts | event persistence, adapter translation, risk-to-execution gate |
| Universe & Data Contract | point-in-time integrity & survivorship control | PIT constituent selection, SHA-256 hash validation, corporate actions |
| Replay/regression | historical behavior remains explainable | fills, corrections, duplicate messages, state rebuild |
| Canonical Simulation | strategy logic under realistic venue frictions | commissions, bid-ask spread, slippage impact, borrow fees |
| Walk-forward/Monte Carlo | robustness beyond fitted history | out-of-sample periods, parameter perturbation, drawdown distribution |
| Paper trading | real external interaction without capital | broker acknowledgements, timing, reconnection, reconciliation |
| Chaos/recovery | safe degradation | disconnect, restart, stale data, store outage, duplicate delivery |
| Performance | SLO and capacity compliance | p95/p99 gate latency, throughput, memory under representative load |

## Required invariants

Test that rejected intents never reach a broker adapter; duplicate submission cannot create duplicate orders; kill switch blocks routing and cannot silently reset; an unresolved reconciliation discrepancy prevents live operation; a restart restores state or halts; simulations fail closed on unverified data digests; promotion gates reject uncertified exploratory evidence; schema changes retain declared compatibility; and every event can be correlated to its decision and configuration version.

## Quality gates

Unit and integration tests run on every change. Contract, replay, simulation, and migration tests run for affected domains. A release candidate runs a pinned regression suite and records environment, inputs, artifacts, and baselines. Risk/execution releases require paper-session evidence, chaos/recovery evidence, and human sign-off. Coverage is a floor, not proof: require meaningful branch coverage for safety decisions and a reviewed exception for generated/adapted code; never use a percentage to excuse untested paths.

## Test data and determinism

Use licensed, versioned fixtures; redact account and personal data; freeze clocks, random seeds, and configuration. Tests must not call live brokers or use production credentials. Golden event streams include normal, partial-fill, reject, disconnect, correction, and restart paths. Performance results compare the same workload and hardware class to a recorded baseline.

