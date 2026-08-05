"""Multi-Stage Risk Circuit Breaker & Order Rate Throttling for TITAN."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BreakerStage(str, Enum):
    NORMAL = "NORMAL"
    THROTTLED = "THROTTLED"
    DEGRADED = "DEGRADED"
    TRIPPED = "TRIPPED"


@dataclass
class CircuitBreakerConfig:
    max_intents_per_second: int = 10
    max_intents_per_minute: int = 100
    max_consecutive_broker_errors: int = 3
    cooldown_seconds: float = 30.0
    trip_on_max_errors: bool = True


@dataclass
class CircuitBreakerStatus:
    stage: BreakerStage
    consecutive_errors: int
    intents_last_second: int
    intents_last_minute: int
    cooldown_remaining_seconds: float
    reason: str = ""


class CircuitBreaker:
    """Multi-stage risk circuit breaker protecting execution pipelines from runaway orders."""

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._stage = BreakerStage.NORMAL
        self._consecutive_errors = 0
        self._last_error_time = 0.0
        self._cooldown_until = 0.0
        self._intent_timestamps: list[float] = []
        self._reason = ""

    @property
    def stage(self) -> BreakerStage:
        self._evaluate_cooldown()
        return self._stage

    def record_intent(self) -> tuple[bool, str]:
        """Record an incoming order intent. Returns (allowed, rejection_reason)."""
        now = time.monotonic()
        self._evaluate_cooldown()

        if self._stage == BreakerStage.TRIPPED:
            return False, f"Circuit breaker TRIPPED: {self._reason}"

        if self._stage == BreakerStage.DEGRADED:
            remaining = max(0.0, self._cooldown_until - now)
            return False, f"Circuit breaker DEGRADED (cooldown active for {remaining:.1f}s)"

        # Prune intent timestamps older than 60s
        self._intent_timestamps = [t for t in self._intent_timestamps if now - t <= 60.0]

        intents_last_sec = sum(1 for t in self._intent_timestamps if now - t <= 1.0)
        intents_last_min = len(self._intent_timestamps)

        if intents_last_sec >= self.config.max_intents_per_second:
            self._stage = BreakerStage.THROTTLED
            self._reason = f"Rate limit exceeded: {intents_last_sec+1}/{self.config.max_intents_per_second} per second"
            return False, self._reason

        if intents_last_min >= self.config.max_intents_per_minute:
            self._stage = BreakerStage.THROTTLED
            self._reason = f"Rate limit exceeded: {intents_last_min+1}/{self.config.max_intents_per_minute} per minute"
            return False, self._reason

        self._intent_timestamps.append(now)
        self._stage = BreakerStage.NORMAL
        self._reason = ""
        return True, ""

    def record_error(self, error_msg: str = "") -> BreakerStage:
        """Record a broker submit or transport error."""
        now = time.monotonic()
        self._consecutive_errors += 1
        self._last_error_time = now

        if self._consecutive_errors >= self.config.max_consecutive_broker_errors:
            if self.config.trip_on_max_errors:
                self._stage = BreakerStage.TRIPPED
                self._reason = f"Consecutive broker errors reached threshold ({self._consecutive_errors}): {error_msg}"
            else:
                self._stage = BreakerStage.DEGRADED
                self._cooldown_until = now + self.config.cooldown_seconds
                self._reason = f"Entering degraded cooldown for {self.config.cooldown_seconds}s: {error_msg}"
        return self._stage

    def record_success(self) -> None:
        """Record a successful order acknowledgement or fill."""
        self._consecutive_errors = 0
        if self._stage in (BreakerStage.NORMAL, BreakerStage.THROTTLED, BreakerStage.DEGRADED):
            now = time.monotonic()
            if now >= self._cooldown_until:
                self._stage = BreakerStage.NORMAL
                self._reason = ""

    def manual_trip(self, reason: str = "Manual emergency trip") -> None:
        """Manually trip the circuit breaker into hard emergency state."""
        self._stage = BreakerStage.TRIPPED
        self._reason = reason

    def reset(self) -> None:
        """Reset circuit breaker back to NORMAL state."""
        self._stage = BreakerStage.NORMAL
        self._consecutive_errors = 0
        self._cooldown_until = 0.0
        self._intent_timestamps.clear()
        self._reason = ""

    def get_status(self) -> CircuitBreakerStatus:
        now = time.monotonic()
        self._evaluate_cooldown()
        sec_count = sum(1 for t in self._intent_timestamps if now - t <= 1.0)
        min_count = len([t for t in self._intent_timestamps if now - t <= 60.0])
        cooldown_rem = max(0.0, self._cooldown_until - now)

        return CircuitBreakerStatus(
            stage=self._stage,
            consecutive_errors=self._consecutive_errors,
            intents_last_second=sec_count,
            intents_last_minute=min_count,
            cooldown_remaining_seconds=cooldown_rem,
            reason=self._reason,
        )

    def _evaluate_cooldown(self) -> None:
        if self._stage == BreakerStage.DEGRADED:
            if time.monotonic() >= self._cooldown_until:
                self._stage = BreakerStage.NORMAL
                self._reason = ""
