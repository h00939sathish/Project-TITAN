# Benchmark: Replay

**Date:** 2026-07-13
**Commit:** fee704f
**Hardware:** 13th Gen Intel(R) Core(TM) i5-13420H, 12 logical cores, 2.1 GHz, 15.7 GB RAM, Windows 11 Home

## Command

```bash
python scripts/bench.py --subsystem replay --iterations 1000
```

## Results

```
TITAN Benchmark Runner
Commit: fee704f
Subsystem: replay
Iterations: 1,000
--------------------------------------------------

=== Replay benchmark ===
Total events: 1,000
Replay time: 3.29 ms
Throughput: 303,536 events/s
Estimated 1M events: 3.29 s
```

## Budget comparison

| Metric | Budget | Measured | Status |
|---|---|---|---|
| Throughput, replay (1M events) | <15 s | 3.29 s (estimated from 1000) | ✅ Pass |
| Determinism | 100% identical | ✅ (existing replays tests) | ✅ |

## Reproduction

```bash
python scripts/bench.py --subsystem replay --iterations 100000
```
