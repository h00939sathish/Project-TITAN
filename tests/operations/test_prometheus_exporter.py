"""Unit & integration tests for Prometheus exporter and MetricsRegistry."""

import time
import urllib.request
import pytest

from titan.operations.metrics import MetricsRegistry, MetricValue
from titan.operations.export import PrometheusExporter, format_prometheus_text


class TestMetricsRegistry:
    def test_counter_and_gauge(self):
        reg = MetricsRegistry()
        c = reg.counter("test_counter")
        g = reg.gauge("test_gauge")

        c.inc(5.0, tags={"symbol": "AAPL"})
        g.set(100.5, tags={"account": "paper-1"})

        snap = reg.snapshot()
        assert snap["test_counter"] == 5.0
        assert snap["test_gauge"] == 100.5

        metrics = reg.snapshot_metrics()
        assert len(metrics) == 2

    def test_histogram_observation_and_buckets(self):
        reg = MetricsRegistry()
        h = reg.histogram("test_latency", buckets=(0.01, 0.05, 0.1))

        h.observe(0.005)
        h.observe(0.02)
        h.observe(0.15)

        assert h.count == 3
        assert abs(h.sum - 0.175) < 1e-6
        counts = h.bucket_counts
        assert counts[0.01] == 1
        assert counts[0.05] == 2
        assert counts[0.1] == 2
        assert counts[float("inf")] == 3


class TestPrometheusExporter:
    def test_format_prometheus_text(self):
        reg = MetricsRegistry()
        c = reg.counter("titan_orders_total")
        g = reg.gauge("titan_equity")
        h = reg.histogram("titan_latency", buckets=(0.05, 0.1))

        c.inc(1, tags={"status": "filled"})
        g.set(100000.0)
        h.observe(0.02)

        text = format_prometheus_text(reg)

        assert "# HELP titan_orders_total" in text
        assert "# TYPE titan_orders_total counter" in text
        assert 'titan_orders_total{status="filled"} 1.0' in text
        assert "titan_equity 100000.0" in text
        assert 'titan_latency_bucket{le="0.05"} 1' in text
        assert "titan_latency_count 1" in text

    def test_http_exporter_server_lifecycle_and_endpoint(self):
        reg = MetricsRegistry()
        reg.gauge("titan_test_metric").set(42.0)

        exporter = PrometheusExporter(reg)
        port = exporter.start(port=9190)
        assert port >= 9190

        try:
            # Test /metrics endpoint
            url = f"http://localhost:{port}/metrics"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8")
                assert "titan_test_metric 42.0" in body

            # Test /health endpoint
            url_health = f"http://localhost:{port}/health"
            with urllib.request.urlopen(url_health, timeout=2.0) as resp:
                assert resp.status == 200
                assert resp.read() == b"OK"
        finally:
            exporter.stop()
