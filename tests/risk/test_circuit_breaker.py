"""Unit tests for Multi-Stage Risk Circuit Breaker."""

import time
import pytest

from titan.risk.circuit_breaker import (
    BreakerStage,
    CircuitBreaker,
    CircuitBreakerConfig,
)


class TestCircuitBreaker:
    def test_normal_intent_allowed(self):
        cb = CircuitBreaker(CircuitBreakerConfig(max_intents_per_second=5))
        ok, msg = cb.record_intent()
        assert ok is True
        assert msg == ""
        assert cb.stage == BreakerStage.NORMAL

    def test_rate_throttling_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig(max_intents_per_second=3))
        for _ in range(3):
            ok, _ = cb.record_intent()
            assert ok is True

        # 4th intent in same second triggers THROTTLED
        ok, msg = cb.record_intent()
        assert ok is False
        assert "Rate limit exceeded" in msg
        assert cb.stage == BreakerStage.THROTTLED

    def test_consecutive_errors_degraded_cooldown(self):
        cfg = CircuitBreakerConfig(
            max_consecutive_broker_errors=3,
            cooldown_seconds=0.2,
            trip_on_max_errors=False,
        )
        cb = CircuitBreaker(cfg)

        cb.record_error("timeout 1")
        cb.record_error("timeout 2")
        assert cb.stage == BreakerStage.NORMAL

        stage = cb.record_error("timeout 3")
        assert stage == BreakerStage.DEGRADED

        ok, msg = cb.record_intent()
        assert ok is False
        assert "DEGRADED" in msg

        # Wait for cooldown to expire
        time.sleep(0.25)
        assert cb.stage == BreakerStage.NORMAL
        ok, _ = cb.record_intent()
        assert ok is True

    def test_consecutive_errors_trips_breaker(self):
        cfg = CircuitBreakerConfig(
            max_consecutive_broker_errors=2,
            trip_on_max_errors=True,
        )
        cb = CircuitBreaker(cfg)

        cb.record_error("err 1")
        stage = cb.record_error("err 2")
        assert stage == BreakerStage.TRIPPED

        ok, msg = cb.record_intent()
        assert ok is False
        assert "TRIPPED" in msg

    def test_manual_trip_and_reset(self):
        cb = CircuitBreaker()
        cb.manual_trip("Emergency manual trip")
        assert cb.stage == BreakerStage.TRIPPED

        ok, msg = cb.record_intent()
        assert ok is False
        assert "Emergency manual trip" in msg

        cb.reset()
        assert cb.stage == BreakerStage.NORMAL
        ok, _ = cb.record_intent()
        assert ok is True
