"""In-memory metrics for TITAN operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import json


@dataclass
class MetricValue:
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""


class Counter:
    def __init__(self, name: str, registry: "MetricsRegistry"):
        self._name = name
        self._registry = registry
        self._value = 0

    def inc(self, amount: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self._value += amount
        self._registry.store(MetricValue(
            name=self._name, value=self._value, tags=tags or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    @property
    def value(self) -> float:
        return self._value


class Gauge:
    def __init__(self, name: str, registry: "MetricsRegistry"):
        self._name = name
        self._registry = registry
        self._value = 0.0

    def set(self, value: float, tags: dict[str, str] | None = None) -> None:
        self._value = value
        self._registry.store(MetricValue(
            name=self._name, value=value, tags=tags or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    @property
    def value(self) -> float:
        return self._value


class MetricsRegistry:
    def __init__(self):
        self._metrics: dict[str, MetricValue] = {}

    def store(self, mv: MetricValue) -> None:
        self._metrics[mv.name] = mv

    def counter(self, name: str) -> Counter:
        return Counter(name, self)

    def gauge(self, name: str) -> Gauge:
        return Gauge(name, self)

    def snapshot(self) -> dict[str, float]:
        return {k: v.value for k, v in self._metrics.items()}

    def dump_json(self) -> str:
        return json.dumps(self.snapshot(), default=str, indent=2)
