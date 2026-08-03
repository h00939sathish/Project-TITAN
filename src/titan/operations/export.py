"""Prometheus export and HTTP server for TITAN operational metrics."""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .metrics import MetricsRegistry


def format_prometheus_text(registry: MetricsRegistry) -> str:
    """Format all metrics in the registry into Prometheus exposition text format."""
    lines: list[str] = []
    seen_headers: set[str] = set()

    for mv in registry.snapshot_metrics():
        base_name = mv.name
        # Strip sum/count suffix if part of histogram for base help/type header
        metric_type = mv.metric_type or "gauge"

        if base_name not in seen_headers:
            lines.append(f"# HELP {base_name} TITAN operational metric: {base_name}")
            lines.append(f"# TYPE {base_name} {metric_type}")
            seen_headers.add(base_name)

        if mv.tags:
            tag_str = ",".join(f'{k}="{v}"' for k, v in sorted(mv.tags.items()))
            lines.append(f"{mv.name}{{{tag_str}}} {mv.value}")
        else:
            lines.append(f"{mv.name} {mv.value}")

    # Process Histograms if present
    for h_name, hist in registry.get_histograms().items():
        if h_name not in seen_headers:
            lines.append(f"# HELP {h_name} Distribution histogram for {h_name}")
            lines.append(f"# TYPE {h_name} histogram")
            seen_headers.add(h_name)

        for le, count in hist.bucket_counts.items():
            le_str = "+Inf" if le == float("inf") else str(le)
            lines.append(f'{h_name}_bucket{{le="{le_str}"}} {count}')
        lines.append(f"{h_name}_sum {hist.sum}")
        lines.append(f"{h_name}_count {hist.count}")

    lines.append("")  # Trailing newline required by Prometheus text format
    return "\n".join(lines)


class _MetricsHTTPHandler(BaseHTTPRequestHandler):
    registry: MetricsRegistry | None = None

    def do_GET(self) -> None:
        if self.path in ("/metrics", "/metrics/"):
            if self.registry:
                content = format_prometheus_text(self.registry).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(500, "Registry uninitialized")
        elif self.path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP server access logs to keep stdout clean."""
        pass


class PrometheusExporter:
    """HTTP Exporter serving TITAN metrics at /metrics in standard Prometheus text format."""

    def __init__(self, registry: MetricsRegistry):
        self._registry = registry
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None

    def start(self, port: int | None = None) -> int:
        """Start background HTTP server on specified port (default: PROMETHEUS_PORT env or 9090)."""
        if self._server is not None:
            return self._port or 9090

        if port is None:
            port = int(os.environ.get("PROMETHEUS_PORT", "9090"))

        handler_class = _MetricsHTTPHandler
        handler_class.registry = self._registry

        # Attempt port binding with automatic fallback if bound
        for p in range(port, port + 10):
            try:
                self._server = HTTPServer(("0.0.0.0", p), handler_class)
                self._port = p
                break
            except OSError:
                continue

        if not self._server:
            raise RuntimeError(f"Could not bind Prometheus HTTP server on ports {port}-{port+9}")

        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="PrometheusExporter"
        )
        self._thread.start()
        return self._port

    def stop(self) -> None:
        """Shutdown background HTTP server cleanly."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def export_text(self) -> str:
        """Return Prometheus text representation directly as string."""
        return format_prometheus_text(self._registry)

    @property
    def port(self) -> int | None:
        return self._port
