# Task G2: Structured logging wired into runtime

## Goal

Create a structured JSON logger and wire it into the risk gate, adapter, reconciliation, and health reporting paths so that running the vertical slice produces JSON-structured logs with correlation_ids tracing each intent.

## Files

- Create: `src/titan/operations/logging.py` — LogEvent, LogSeverity, StructuredLogger
- Modify: `src/titan/operations/telemetry.py` — wire StructuredLogger into HealthReporter.health()
- Create: `src/titan/operations/_logging_integration.py` — convenience functions to log risk decisions, adapter events, reconciliation results with minimal boilerplate
- Create: `tests/operations/test_logging.py` — tests for the logger

## Implementation details

### src/titan/operations/logging.py

```python
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
```

### src/titan/operations/__init__.py

Update to expose the logger:
```python
"""TITAN operations package — telemetry, logging, and health reporting."""
from titan.operations.logging import StructuredLogger, LogSeverity, LogEvent
from titan.operations.telemetry import HealthReporter, SystemHealth, SystemState, ComponentHealth
```

### src/titan/operations/_logging_integration.py

Convenience functions that log risk decisions, adapter operations, and reconciliation results:

```python
"""Integration helpers that wire StructuredLogger into runtime paths."""

from titan.operations.logging import StructuredLogger, LogSeverity


def log_risk_decision(logger: StructuredLogger, intent_id: str, accepted: bool,
                      reason: str | None, correlation_id: str = "",
                      instrument_id: str = "") -> None:
    if accepted:
        logger.info("risk_gate", f"Intent {intent_id} accepted",
                    correlation_id=correlation_id,
                    payload={"intent_id": intent_id, "verdict": "accepted", "instrument_id": instrument_id})
    else:
        logger.warning("risk_gate", f"Intent {intent_id} rejected: {reason}",
                       correlation_id=correlation_id,
                       payload={"intent_id": intent_id, "verdict": "rejected",
                                "reason": reason, "instrument_id": instrument_id})


def log_adapter_event(logger: StructuredLogger, event: str, order_id: str,
                      instrument_id: str = "", correlation_id: str = "",
                      payload: dict | None = None) -> None:
    logger.info("adapter", f"Order {order_id} {event}",
                correlation_id=correlation_id,
                payload={"order_id": order_id, "event": event,
                         "instrument_id": instrument_id, **(payload or {})})


def log_reconciliation(logger: StructuredLogger, result: dict,
                       correlation_id: str = "") -> None:
    severity = LogSeverity.WARNING if result.get("has_drift") else LogSeverity.INFO
    logger._log(severity, "reconciliation", "Reconciliation completed",
                correlation_id=correlation_id, payload=result)
```

### Modifying telemetry.py

Add logging to HealthReporter.health() — after computing the health report, log it at INFO level if healthy, WARNING if degraded:

```python
def health(self, state: SystemState = SystemState.ACTIVE, logger: StructuredLogger | None = None) -> SystemHealth:
    # ... existing computation ...
    if logger is not None:
        log_level = "WARNING" if issues else "INFO"
        logger.info("health_reporter", f"Health check: {summary}",
                    payload=h.to_dict())
    return h
```

Add import to telemetry.py:
```python
from titan.operations.logging import StructuredLogger
```

### tests/operations/test_logging.py

```python
"""Tests for structured logging."""

import json
import io
from titan.operations.logging import StructuredLogger, LogSeverity, LogEvent


class TestStructuredLogger:
    def test_outputs_json(self):
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        logger.info("test", "hello world")
        output = buf.getvalue()
        data = json.loads(output)
        assert data["component"] == "test"
        assert data["message"] == "hello world"
        assert data["severity"] == "INFO"

    def test_severity_filtering(self):
        buf = io.StringIO()
        logger = StructuredLogger(min_severity=LogSeverity.WARNING, output=buf)
        logger.info("test", "should not appear")
        logger.warning("test", "should appear")
        output = buf.getvalue()
        assert "should not appear" not in output
        assert "should appear" in output

    def test_correlation_id_in_output(self):
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        logger.info("risk", "intent evaluated", correlation_id="corr-123")
        data = json.loads(buf.getvalue())
        assert data["correlation_id"] == "corr-123"

    def test_payload_in_output(self):
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        logger.info("adapter", "order filled", payload={"order_id": "ord-1", "fill_qty": 100})
        data = json.loads(buf.getvalue())
        assert data["payload"]["order_id"] == "ord-1"
        assert data["payload"]["fill_qty"] == 100

    def test_missing_fields_empty_strings(self):
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        logger.info("test", "minimal")
        data = json.loads(buf.getvalue())
        assert data["correlation_id"] == ""
        assert data["causation_id"] == ""

    def test_log_event_directly(self):
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        event = LogEvent(severity=LogSeverity.ERROR, component="test",
                         message="direct event", correlation_id="cid-1")
        logger.log_event(event)
        data = json.loads(buf.getvalue())
        assert data["severity"] == "ERROR"
        assert data["message"] == "direct event"

    def test_logging_integration_helpers(self):
        import io
        from titan.operations._logging_integration import log_risk_decision, log_adapter_event
        buf = io.StringIO()
        logger = StructuredLogger(output=buf)
        log_risk_decision(logger, "int-1", True, None, correlation_id="corr-1")
        log_adapter_event(logger, "submitted", "ord-1", correlation_id="corr-1")
        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert data["correlation_id"] == "corr-1"
```

## Acceptance criteria

- `python -m pytest tests/operations/test_logging.py -v` passes (7 tests)
- `python -m pytest tests/operations/ -v` passes (7 telemetry + 7 logging = 14 tests)
- `python -m pytest tests/ -v` passes (no regressions)
- StructuredLogger produces valid JSON lines with all required fields

## Constraints

- No breaking changes to existing HealthReporter API (logger parameter is optional)
- Follow existing codebase patterns (dataclasses, enums, pytest)
- No credentials in source or logs
