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
