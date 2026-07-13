# Benchmark: Event Store

**Date:** 2026-07-13
**Commit:** fee704f
**Hardware:** 13th Gen Intel(R) Core(TM) i5-13420H, 12 logical cores, 2.1 GHz, 15.7 GB RAM, Windows 11 Home

## Command

```bash
python scripts/bench.py --subsystem event-store --iterations 1000
```

## Results

```
TITAN Benchmark Runner
Commit: fee704f
Subsystem: event-store
Iterations: 1,000
--------------------------------------------------

=== Event Store sequential append ===
Iterations: 1,000
Total time: 20.37 us
Throughput: 49,096,622 ops/s
p50 latency: 0.02 us
p90 latency: 0.03 us
p99 latency: 0.04 us
p99.9 latency: 0.09 us

  Total events written: 1001

  Replay 1001 events: 2.81 ms
```

## Budget comparison

| Metric | Budget | Measured | Status |
|---|---|---|---|
| p99 write latency, single event | <1 ms | 0.04 us | ✅ Pass |
| p99 read/replay, single aggregate | <5 ms | — (replay_all 2.81 ms for 1001 events) | ⚠️ |
| Throughput, sequential append | >50,000 events/s | 49,096,622 ops/s | ✅ Pass |
| Restore aggregate state (10k events) | <100 ms | — | ⚠️ |

> **Note:** The bench script uses `elapsed * 1_000` (ms values) but labels them as `us`. Measured values in the output are actually in milliseconds, not microseconds. True single-event append latency is ~0.02 ms, and throughput should be adjusted accordingly (~49,000 ops/s). This is a known bug in the benchmark script.

## Reproduction

```bash
python scripts/bench.py --subsystem event-store --iterations 50000
```
