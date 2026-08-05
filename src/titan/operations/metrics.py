"""In-memory metrics for TITAN operations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MetricValue:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""
    metric_type: str = "gauge"  # "counter", "gauge", "histogram"


class Counter:
    def __init__(self, name: str, registry: MetricsRegistry):
        self._name = name
        self._registry = registry
        self._value = 0.0

    def inc(self, amount: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self._value += amount
        self._registry.store(
            MetricValue(
                name=self._name,
                value=self._value,
                tags=tags or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                metric_type="counter",
            )
        )

    @property
    def value(self) -> float:
        return self._value


class Gauge:
    def __init__(self, name: str, registry: MetricsRegistry):
        self._name = name
        self._registry = registry
        self._value = 0.0

    def set(self, value: float, tags: dict[str, str] | None = None) -> None:
        self._value = value
        self._registry.store(
            MetricValue(
                name=self._name,
                value=value,
                tags=tags or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                metric_type="gauge",
            )
        )

    @property
    def value(self) -> float:
        return self._value


DEFAULT_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class Histogram:
    """Histogram metric for measuring latency distributions and quantities."""

    def __init__(
        self,
        name: str,
        registry: MetricsRegistry,
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ):
        self._name = name
        self._registry = registry
        self._buckets = sorted(list(buckets))
        self._sum = 0.0
        self._count = 0
        self._bucket_counts: dict[float, int] = {b: 0 for b in self._buckets}
        self._bucket_counts[float("inf")] = 0

    def observe(self, amount: float, tags: dict[str, str] | None = None) -> None:
        self._sum += amount
        self._count += 1
        for b in self._buckets:
            if amount <= b:
                self._bucket_counts[b] += 1
        self._bucket_counts[float("inf")] += 1

        self._registry.store(
            MetricValue(
                name=f"{self._name}_sum",
                value=self._sum,
                tags=tags or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                metric_type="histogram",
            )
        )
        self._registry.store(
            MetricValue(
                name=f"{self._name}_count",
                value=float(self._count),
                tags=tags or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                metric_type="histogram",
            )
        )

    @property
    def count(self) -> int:
        return self._count

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def bucket_counts(self) -> dict[float, int]:
        return dict(self._bucket_counts)


class MetricsRegistry:
    def __init__(self):
        self._metrics: dict[str, MetricValue] = {}
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def store(self, mv: MetricValue) -> None:
        key = mv.name
        if mv.tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(mv.tags.items()))
            key = f"{mv.name}{{{tag_str}}}"
        self._metrics[key] = mv

    def counter(self, name: str) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, self)
        return self._counters[name]

    def gauge(self, name: str) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, self)
        return self._gauges[name]

    def histogram(self, name: str, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, self, buckets=buckets)
        return self._histograms[name]

    def snapshot(self) -> dict[str, float]:
        """Returns flat metric_name -> float_value mapping for simple exporters."""
        res: dict[str, float] = {}
        for key, mv in self._metrics.items():
            res[mv.name] = mv.value
        return res

    def snapshot_metrics(self) -> list[MetricValue]:
        """Returns complete list of registered MetricValues with tags and types."""
        return list(self._metrics.values())

    def get_histograms(self) -> dict[str, Histogram]:
        return dict(self._histograms)

    def dump_json(self) -> str:
        return json.dumps(self.snapshot(), default=str, indent=2)
