"""Structured JSON logging for TITAN operations."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
import sys


class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEvent:
    timestamp: str = ""
    severity: LogSeverity = LogSeverity.INFO
    component: str = ""
    message: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        if not d["timestamp"]:
            d["timestamp"] = datetime.now(timezone.utc).isoformat()
        return json.dumps(d, default=str)


class StructuredLogger:
    """Writes JSON-structured log lines to an output stream."""

    def __init__(self, min_severity: LogSeverity = LogSeverity.INFO, output=None):
        self._min = min_severity
        self._output = output or sys.stdout

    @property
    def min_severity(self) -> LogSeverity:
        return self._min

    def log_event(self, event: LogEvent) -> None:
        severity_order = {
            LogSeverity.DEBUG: 0, LogSeverity.INFO: 1,
            LogSeverity.WARNING: 2, LogSeverity.ERROR: 3, LogSeverity.CRITICAL: 4,
        }
        if severity_order.get(event.severity, 1) < severity_order.get(self._min, 1):
            return
        print(event.to_json(), file=self._output, flush=True)

    def _log(self, severity: LogSeverity, component: str, message: str,
             correlation_id: str = "", causation_id: str = "",
             payload: dict[str, Any] | None = None) -> None:
        event = LogEvent(
            severity=severity, component=component, message=message,
            correlation_id=correlation_id, causation_id=causation_id,
            payload=payload or {},
        )
        self.log_event(event)

    def info(self, component: str, message: str, **kwargs) -> None:
        self._log(LogSeverity.INFO, component, message, **kwargs)

    def warning(self, component: str, message: str, **kwargs) -> None:
        self._log(LogSeverity.WARNING, component, message, **kwargs)

    def error(self, component: str, message: str, **kwargs) -> None:
        self._log(LogSeverity.ERROR, component, message, **kwargs)
