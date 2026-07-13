#!/usr/bin/env python3
"""Reproducible benchmark runner for TITAN subsystems.

Usage:
    python scripts/bench.py --subsystem risk --iterations 10000
    python scripts/bench.py --subsystem event-store --iterations 50000
    python scripts/bench.py --subsystem replay --iterations 100000
"""

import argparse
import statistics
import time
import sys
import os


def p99(values: list[float]) -> float:
    """Compute p99 latency from sorted values."""
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.99)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def format_results(title: str, latencies: list[float], count: int, unit: str = "us") -> str:
    """Format benchmark results as a string table."""
    total_time = sum(latencies)
    throughput = count / total_time * 1_000_000 if total_time > 0 else 0
    return f"""
=== {title} ===
Iterations: {count:,}
Total time: {total_time:.2f} {unit}
Throughput: {throughput:,.0f} ops/s
p50 latency: {statistics.median(latencies):.2f} {unit}
p90 latency: {sorted(latencies)[int(count * 0.90)]:.2f} {unit}
p99 latency: {p99(latencies):.2f} {unit}
p99.9 latency: {sorted(latencies)[int(count * 0.999)]:.2f} {unit}
"""


def bench_risk_gate(iterations: int = 10000):
    """Benchmark RiskGate.evaluate() latency."""
    from titan._core import RiskConfig, RiskGate, TradeIntent

    config = RiskConfig.default()
    gate = RiskGate(config)
    intent = TradeIntent("bench", "pkg-v1", "acct-1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", price="150")

    latencies: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        gate.evaluate(intent, None, None, None, None)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed * 1_000_000)  # convert to μs

    print(format_results("Risk Gate evaluate()", latencies, iterations))


def bench_event_store(iterations: int = 50000):
    """Benchmark EventStore sequential append throughput."""
    from titan._core import EventStore, EventEnvelope
    import uuid

    store = EventStore(":memory:")
    base_env = EventEnvelope("Bench", "benchmark", "agg-1", "bench", "{}")

    # Warm up
    env = EventEnvelope.from_json(base_env.to_json())
    store.append(env)

    latencies: list[float] = []
    for i in range(iterations):
        env = EventEnvelope("Bench", "benchmark", f"agg-{i % 100}", "bench", "{}")
        start = time.perf_counter()
        store.append(env)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed * 1_000)  # convert to μs

    print(format_results("Event Store sequential append", latencies, iterations))
    print(f"  Total events written: {store.count()}")

    # Benchmark replay
    replay_start = time.perf_counter()
    all_events = store.replay_all()
    replay_time = time.perf_counter() - replay_start
    print(f"\n  Replay {len(all_events)} events: {replay_time * 1000:.2f} ms")


def bench_replay(iterations: int = 100000):
    """Benchmark replay throughput."""
    from titan._core import EventStore, EventEnvelope

    store = EventStore(":memory:")

    # Pre-populate events
    for i in range(iterations):
        env = EventEnvelope("Bench", "benchmark", f"agg-{i % 100}", "bench", "{}")
        store.append(env)

    # Benchmark replay_all
    start = time.perf_counter()
    events = store.replay_all()
    elapsed = time.perf_counter() - start

    total_events = len(events)
    throughput = total_events / elapsed if elapsed > 0 else 0
    print(f"""
=== Replay benchmark ===
Total events: {total_events:,}
Replay time: {elapsed * 1000:.2f} ms
Throughput: {throughput:,.0f} events/s
Estimated 1M events: {(1_000_000 / throughput):.2f} s
""")


def get_git_sha() -> str:
    """Get current git commit SHA."""
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="TITAN Benchmark Runner")
    parser.add_argument("--subsystem", choices=["risk", "event-store", "replay"], required=True)
    parser.add_argument("--iterations", type=int, default=10000)
    args = parser.parse_args()

    print(f"TITAN Benchmark Runner")
    print(f"Commit: {get_git_sha()}")
    print(f"Subsystem: {args.subsystem}")
    print(f"Iterations: {args.iterations:,}")
    print(f"{'-' * 50}")

    benchmarks = {
        "risk": bench_risk_gate,
        "event-store": bench_event_store,
        "replay": bench_replay,
    }
    benchmarks[args.subsystem](args.iterations)


if __name__ == "__main__":
    main()
