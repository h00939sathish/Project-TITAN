"""Tests for metrics emission."""

from titan.operations.metrics import Counter, Gauge, MetricsRegistry
from titan.operations._metrics_integration import get_registry


class TestMetricsCore:
    def test_counter_increments(self):
        reg = MetricsRegistry()
        c = reg.counter("test_count")
        assert c.value == 0
        c.inc()
        assert c.value == 1
        c.inc(5)
        assert c.value == 6

    def test_gauge_sets_value(self):
        reg = MetricsRegistry()
        g = reg.gauge("test_gauge")
        assert g.value == 0.0
        g.set(42.5)
        assert g.value == 42.5
        g.set(-1.0)
        assert g.value == -1.0

    def test_registry_snapshot(self):
        reg = MetricsRegistry()
        c = reg.counter("a")
        g = reg.gauge("b")
        c.inc(3)
        g.set(1.5)
        snap = reg.snapshot()
        assert snap["a"] == 3
        assert snap["b"] == 1.5

    def test_dump_json(self):
        reg = MetricsRegistry()
        c = reg.counter("x")
        c.inc(10)
        output = reg.dump_json()
        import json
        parsed = json.loads(output)
        assert parsed["x"] == 10

    def test_multiple_counters_independent(self):
        reg = MetricsRegistry()
        c1 = reg.counter("first")
        c2 = reg.counter("second")
        c1.inc(1)
        c2.inc(99)
        assert c1.value == 1
        assert c2.value == 99

    def test_module_registry_is_singleton(self):
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2


class TestMetricsIntegration:
    def test_risk_metrics_via_integration_helpers(self):
        from titan._core import RiskConfig, RiskGate, TradingState, EventStore
        from titan.operations._metrics_integration import (
            intents_evaluated, intents_rejected, kill_switch_triggered,
            trading_state_changed, positions_open, orders_submitted, orders_filled,
        )
        from titan.operations.metrics import MetricsRegistry

        config = RiskConfig.default()
        gate = RiskGate(config)

        # Simulate: evaluate an intent (risk decision)
        intents_evaluated.inc()
        intents_evaluated.inc()
        assert intents_evaluated.value == 2

        # Simulate: reject an intent
        intents_rejected.inc()
        assert intents_rejected.value == 1

        # Simulate: trigger kill switch
        kill_switch_triggered.inc()
        assert kill_switch_triggered.value == 1

        # Simulate: portfolio update
        positions_open.set(3)
        assert positions_open.value == 3

        # Simulate: order events
        orders_submitted.inc()
        orders_filled.inc()
        assert orders_submitted.value == 1
        assert orders_filled.value == 1
