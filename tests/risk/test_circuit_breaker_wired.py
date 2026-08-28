"""Integration tests proving CircuitBreaker is wired into PaperTradingEngine.

These tests fail if the breaker is removed from the order submission pipeline.
They do NOT duplicate the unit tests in test_circuit_breaker.py — they verify
only that the wiring exists and functions in the engine context.
"""

import pytest
from fixtures.session_init import initialize_fresh

from titan._core import (
    ContractType,
    Instrument,
    InstrumentId,
    Money,
    RiskConfig,
    ReconciliationConfig,
    TradeIntent,
)
from titan.execution import (
    PaperConfig,
    PaperTradingEngine,
    SimFillQuality,
    SimulatedAdapter,
)
from titan.risk.circuit_breaker import BreakerStage, CircuitBreakerConfig


def _config() -> PaperConfig:
    risk_config = RiskConfig(
        ["AAPL", "MSFT"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )
    return PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="test-1",
        state_path="",
    )


def _intent(instrument="AAPL", side="BUY", qty="10") -> TradeIntent:
    from datetime import datetime, timezone
    return TradeIntent(
        "test-strat", "test-pkg", "test-1",
        instrument, side, qty, "MARKET", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        certificate_ref="test-cert",
    )


def _make_engine(max_per_sec=3):
    """Build an engine with a tight circuit breaker for testing."""
    config = _config()
    adapter = SimulatedAdapter()
    adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
    engine = PaperTradingEngine(config, adapter)
    # Override with a tighter config for testing
    engine.circuit_breaker = __import__(
        "titan.risk.circuit_breaker", fromlist=["CircuitBreaker"]
    ).CircuitBreaker(CircuitBreakerConfig(
        max_intents_per_second=max_per_sec,
        max_intents_per_minute=100,
        max_consecutive_broker_errors=2,
        trip_on_max_errors=True,
    ))
    initialize_fresh(engine)
    engine.start()
    for sym in ("AAPL", "MSFT"):
        engine.register_instrument(
            Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
    return engine


class TestCircuitBreakerWired:
    """Prove the breaker is in the order path, not just importable."""

    def test_engine_has_circuit_breaker_attribute(self):
        engine = PaperTradingEngine(_config(), SimulatedAdapter())
        assert hasattr(engine, "circuit_breaker")
        assert engine.circuit_breaker.stage == BreakerStage.NORMAL

    def test_rate_limit_rejects_intent_through_engine(self):
        """Submit more intents than the per-second limit; verify rejection
        comes from the circuit breaker, not the risk gate."""
        engine = _make_engine(max_per_sec=2)
        # First two should pass (or be rejected by risk gate — either way,
        # the breaker records them). Third must hit the breaker.
        results = [engine.submit_intent(_intent()) for _ in range(3)]
        # At least the last one must be rejected by the circuit breaker
        breaker_rejections = [
            r for r in results
            if not r.accepted and r.rejection_reason and "Circuit breaker" in r.rejection_reason
        ]
        assert len(breaker_rejections) >= 1, (
            "Expected at least one rejection from circuit breaker rate limit, "
            f"got: {[(r.accepted, r.rejection_reason) for r in results]}"
        )

    def test_consecutive_broker_errors_trip_breaker(self):
        """Simulate broker errors and verify the breaker trips."""
        engine = _make_engine(max_per_sec=100)
        # Manually record errors to simulate broker failures
        engine.circuit_breaker.record_error("broker timeout 1")
        engine.circuit_breaker.record_error("broker timeout 2")
        assert engine.circuit_breaker.stage == BreakerStage.TRIPPED

        # Now submit an intent — it should be rejected by the tripped breaker
        result = engine.submit_intent(_intent())
        assert not result.accepted
        assert "Circuit breaker" in result.rejection_reason

    def test_success_resets_error_counter(self):
        """Verify record_success is called (indirectly) by checking error
        counter doesn't accumulate across successful fills."""
        engine = _make_engine(max_per_sec=100)
        # One error, then a successful order
        engine.circuit_breaker.record_error("transient")
        assert engine.circuit_breaker.get_status().consecutive_errors == 1

        # A successful order through the engine should reset the counter
        result = engine.submit_intent(_intent())
        if result.accepted:
            # If the order was accepted, record_success should have fired
            assert engine.circuit_breaker.get_status().consecutive_errors == 0

    def test_breaker_status_in_engine_status(self):
        """Verify the circuit breaker stage appears in EngineStatus."""
        engine = _make_engine()
        status = engine.status()
        assert status.circuit_breaker_stage == "NORMAL"
        assert status.circuit_breaker_consecutive_errors == 0

    def test_tripped_breaker_visible_in_status(self):
        """Trip the breaker and verify it shows in engine status."""
        engine = _make_engine()
        engine.circuit_breaker.manual_trip("test trip")
        status = engine.status()
        assert status.circuit_breaker_stage == "TRIPPED"
