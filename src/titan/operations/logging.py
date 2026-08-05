import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


_SEVERITY_MAP = {
    LogSeverity.DEBUG: logging.DEBUG,
    LogSeverity.INFO: logging.INFO,
    LogSeverity.WARNING: logging.WARNING,
    LogSeverity.ERROR: logging.ERROR,
    LogSeverity.CRITICAL: logging.CRITICAL,
}


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
    def __init__(self, min_severity: LogSeverity = LogSeverity.INFO, output=None):
        level = _SEVERITY_MAP.get(min_severity, logging.INFO)
        self._logger = logging.getLogger("titan")
        self._logger.setLevel(level)
        self._logger.handlers.clear()
        handler = logging.StreamHandler(output or sys.stdout)
        handler.setLevel(level)
        self._logger.addHandler(handler)
        self._min = min_severity

    @property
    def min_severity(self) -> LogSeverity:
        return self._min

    def log_event(self, event: LogEvent) -> None:
        self._logger.log(_SEVERITY_MAP.get(event.severity, logging.INFO),
                         event.to_json())

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
