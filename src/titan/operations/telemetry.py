"""System telemetry and health reporting."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


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



