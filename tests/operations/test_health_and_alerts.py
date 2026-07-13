"""Tests for operations telemetry and health reporting."""

from titan.operations.telemetry import HealthReporter, SystemState


class TestHealthReporter:
    def test_starts_healthy_no_components(self):
        hr = HealthReporter()
        h = hr.health()
        assert h.state == SystemState.ACTIVE
        assert h.uptime_seconds >= 0
        assert h.summary == "All systems healthy"

    def test_register_component(self):
        hr = HealthReporter()
        hr.register_component("risk_gate")
        h = hr.health()
        assert "risk_gate" in h.components

    def test_report_healthy(self):
        hr = HealthReporter()
        hr.register_component("event_store")
        hr.report_healthy("event_store", "SQLite connected")
        h = hr.health()
        assert h.components["event_store"].status == "healthy"

    def test_report_degraded(self):
        hr = HealthReporter()
        hr.register_component("adapter")
        hr.report_degraded("adapter", "High latency")
        h = hr.health()
        assert h.components["adapter"].status == "degraded"
        assert "1 component(s)" in h.summary

    def test_report_down(self):
        hr = HealthReporter()
        hr.register_component("broker")
        hr.report_down("broker", "Connection refused")
        h = hr.health()
        assert h.components["broker"].status == "down"

    def test_multiple_components(self):
        hr = HealthReporter()
        for name in ["risk_gate", "event_store", "adapter", "portfolio"]:
            hr.register_component(name)
        hr.report_healthy("risk_gate")
        hr.report_healthy("event_store")
        hr.report_degraded("adapter", "Rate limited")
        hr.report_down("broker", "Timeout")
        h = hr.health(state=SystemState.HALTED)
        assert h.state == SystemState.HALTED
        assert len(h.components) == 5

    def test_health_to_dict(self):
        hr = HealthReporter()
        hr.register_component("risk_gate")
        hr.report_healthy("risk_gate")
        d = hr.health().to_dict()
        assert isinstance(d, dict)
        assert "state" in d
        assert "components" in d
        assert "risk_gate" in d["components"]
