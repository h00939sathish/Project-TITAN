"""Performance test for risk gate latency."""

import time
import pytest
from titan._core import RiskGate, RiskConfig, TradeIntent
from titan.risk.limits import load_config

def make_intent() -> TradeIntent:
    from datetime import datetime, timezone
    return TradeIntent(
        "strat-perf", "pkg-perf", "acct-1", "AAPL",
        "BUY", "100", "LIMIT", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        price="150"
    )

@pytest.mark.benchmark
def test_risk_gate_p99_latency():
    """Validate p99 risk-gate latency is under 50us budget."""
    config = load_config()
    gate = RiskGate(config)
    
    # Pre-warm the JIT / pipelines
    intent = make_intent()
    for _ in range(100):
        gate.evaluate(intent, None, None, None, None, None)
        
    iterations = 20_000
    latencies_ns = []
    
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        gate.evaluate(intent, None, None, None, None, None)
        t1 = time.perf_counter_ns()
        latencies_ns.append(t1 - t0)
        
    latencies_ns.sort()
    
    # p99 index
    p99_idx = int(iterations * 0.99)
    p99_latency_ns = latencies_ns[p99_idx]
    
    p99_latency_us = p99_latency_ns / 1000.0
    
    print(f"\nRisk Gate p99 latency: {p99_latency_us:.2f} us")
    
    # Assert p99 latency < 50us (50,000 ns)
    assert p99_latency_us < 50.0, f"p99 latency {p99_latency_us} us exceeded budget of 50 us"
