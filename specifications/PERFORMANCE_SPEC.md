# Performance Specification

> **Owner:** Core Platform Architecture
> **Status:** Active — Phase -1 baseline
> **Last Review:** 2026-07-13
> **Decision Authority:** Architecture Council

## Measurement methodology

All measurements are taken on the target hardware baseline (TBD in ADR-0002) under a representative workload. Workload characterization and the exact hardware profile are recorded in `knowledge/benchmarks/baseline-*.md` before any optimization.

- **p99 latency:** measured over a 10-minute steady-state window at the 50th-percentile event arrival rate.
- **Throughput:** measured over a 5-minute sustained window with no pre-warmed caches.
- **Memory:** peak RSS and heap allocation rate under the same workload.
- All measurements are reproducible: fixed seed, fixed dataset, recorded artifact digest.

## Budgets

### Risk gate

| Metric | Budget | Criticality |
|---|---|---|
| p99 latency, single intent evaluation | <50 μs | Safety — blocks order path |
| p99 latency, full pipeline (schema → broker health) | <200 μs | Safety |
| Max concurrent evaluations | 10,000/s | Capacity |

### Execution — order lifecycle

| Metric | Budget | Criticality |
|---|---|---|
| p99 latency, intent → submit event persisted | <100 μs | Safety — order latency |
| p99 latency, adapter round-trip (simulated) | <1 ms | Throughput |
| Max active orders tracked | 10,000 | Capacity |

### Event store

| Metric | Budget | Criticality |
|---|---|---|
| p99 write latency, single event | <1 ms | Core path |
| p99 read/replay, single aggregate | <5 ms | Recovery |
| Throughput, sequential append | >50,000 events/s | Throughput |
| Restore aggregate state (10k events) | <100 ms | Recovery |

### Replay / backtest

| Metric | Budget | Criticality |
|---|---|---|
| Throughput, replay (1M events, bar-level) | <15 s | Research velocity |
| Determinism | 100% identical across runs | Correctness |

### Kill switch

| Metric | Budget | Criticality |
|---|---|---|
| p99 latency, state check | <10 μs | Safety |
| p99 latency, state transition (ARMED → TRIGGERED) | <50 μs | Safety |

## Budget adjustment

Budgets are revised only by ADR, with evidence from `knowledge/benchmarks/` that the current budget is impossible or unnecessarily tight for the stated hardware baseline.
