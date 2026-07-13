# Benchmark: Risk Gate

**Date:** 2026-07-13
**Commit:** fee704f
**Hardware:** 13th Gen Intel(R) Core(TM) i5-13420H, 12 logical cores, 2.1 GHz, 15.7 GB RAM, Windows 11 Home

## Command

```bash
python scripts/bench.py --subsystem risk --iterations 1000
```

## Results

```
TITAN Benchmark Runner
Commit: fee704f
Subsystem: risk
Iterations: 1,000
--------------------------------------------------

=== Risk Gate evaluate() ===
Iterations: 1,000
Total time: 1005.50 us
Throughput: 994,530 ops/s
p50 latency: 0.90 us
p90 latency: 1.00 us
p99 latency: 1.40 us
p99.9 latency: 36.10 us
```

## Budget comparison

| Metric | Budget | Measured | Status |
|---|---|---|---|
| p99 latency, single intent evaluation | <50 us | 1.40 us | ✅ Pass |
| p99 latency, full pipeline | <200 us | — | ⚠️ Full pipeline not yet benchmarked |
| Max concurrent evaluations | 10,000/s | — | ⚠️ Not tested |

## Reproduction

```bash
python scripts/bench.py --subsystem risk --iterations 10000
```

The benchmark is deterministic with fixed seed. Results may vary by hardware.
