"""System telemetry and health reporting."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from titan.operations.logging import StructuredLogger


class SystemState(str, Enum):
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    HALTED = "HALTED"
    DEGRADED = "DEGRADED"


@dataclass
class ComponentHealth:
    name: str
    status: str  # "healthy" | "degraded" | "down"
    detail: str = ""
    last_check: str = ""


@dataclass
class SystemHealth:
    state: SystemState = SystemState.ACTIVE
    uptime_seconds: float = 0.0
    components: dict[str, ComponentHealth] = field(default_factory=dict)
    last_reconciliation: str = ""
    summary: str = ""
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "uptime_seconds": self.uptime_seconds,
            "components": {
                k: {"status": v.status, "detail": v.detail, "last_check": v.last_check}
                for k, v in self.components.items()
            },
            "last_reconciliation": self.last_reconciliation,
            "summary": self.summary,
            "checked_at": self.checked_at,
        }


class HealthReporter:
    """Collects component health into a system health report."""

    def __init__(self):
        self._start_time = datetime.now(timezone.utc)
        self._components: dict[str, ComponentHealth] = {}

    def register_component(self, name: str) -> None:
        if name not in self._components:
            self._components[name] = ComponentHealth(
                name=name, status="unknown", last_check=datetime.now(timezone.utc).isoformat()
            )

    def report_healthy(self, name: str, detail: str = "") -> None:
        self._components[name] = ComponentHealth(
            name=name, status="healthy", detail=detail,
            last_check=datetime.now(timezone.utc).isoformat()
        )

    def report_degraded(self, name: str, detail: str) -> None:
        self._components[name] = ComponentHealth(
            name=name, status="degraded", detail=detail,
            last_check=datetime.now(timezone.utc).isoformat()
        )

    def report_down(self, name: str, detail: str) -> None:
        self._components[name] = ComponentHealth(
            name=name, status="down", detail=detail,
            last_check=datetime.now(timezone.utc).isoformat()
        )

    def health(self, state: SystemState = SystemState.ACTIVE, logger: StructuredLogger | None = None) -> SystemHealth:
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        issues = [c for c in self._components.values() if c.status != "healthy"]
        summary = "All systems healthy" if not issues else f"{len(issues)} component(s) degraded/down"
        h = SystemHealth(
            state=state,
            uptime_seconds=uptime,
            components=dict(self._components),
            summary=summary,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        if logger is not None:
            logger.info("health_reporter", f"Health check: {summary}",
                        payload=h.to_dict())
        return h
