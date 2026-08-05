"""Performance testing for deterministic replay throughput."""

import time
import pytest
from titan._core import Money, PortfolioEngine
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.clock import ReplayClock

@pytest.mark.benchmark
def test_replay_throughput_1m_events():
    """Validate replay throughput against PERFORMANCE_SPEC.md budget (1M events <15s)."""
    
    # Pre-generate 1,000,000 mock events to avoid generator overhead in the timed block
    # Using a flat representation or a single pre-allocated list.
    
    # To save memory and time generating, we can just reuse a single dictionary 
    # but that might not accurately reflect memory access.
    # We will generate a compact list of tuples if possible, or just reuse a dict in a loop.
    # Reusing a dict simulates the stream of data without crashing memory.
    
    portfolio = PortfolioEngine("USD", Money("100000", "USD"))
    model = BarConservativeFillModel(slippage_bps=0.5, commission_bps=1.0)
    clock = ReplayClock()
    
    event = {
        "instrument_id": "AAPL",
        "timestamp": "2026-01-01T12:00:00",
        "open": 150.0,
        "high": 152.0,
        "low": 149.0,
        "close": 151.0,
        "volume": 1000
    }
    
    iterations = 1_000_000
    
    start_time = time.perf_counter()
    
    # Simulating the hot-loop of a replay runner
    for _ in range(iterations):
        # We don't advance clock 1M times with strings, let's just do it directly if possible,
        # but to be fair to the test, let's call the functions
        clock.advance_to(event["timestamp"])
        
        # Every 10th event triggers a fill (typical ratio)
        if _ % 10 == 0:
            fill = model.fill(event, "buy", 1)
            # simulate portfolio update
            portfolio.apply_fill(
                event["instrument_id"],
                "buy",
                fill.fill_quantity,
                Money(str(int(fill.fill_price)), "USD"),
            )
            
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print(f"\nProcessed {iterations} events in {duration:.2f} seconds.")
    
    # Assert duration is less than 15 seconds
    assert duration < 15.0, f"Replay throughput {duration:.2f}s exceeded budget of 15.0s"
