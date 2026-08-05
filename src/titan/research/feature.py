"""Feature Registry — declarative, versioned features with lineage."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal


FeatureCategory = Literal[
    "market_structure", "breadth", "volatility",
    "macro", "calendar", "relative_strength", "volume",
]


@dataclass(frozen=True)
class Feature:
    """A single computed feature with full provenance metadata.

    Features are declarative, not functional. The engine computes
    them by looking up the registered compute_fn.
    """

    id: str                                  # e.g. "atr_percentile_20"
    category: FeatureCategory
    inputs: tuple[str, ...]                  # source column names
    frequency: Literal["1D", "1W", "1M", "intraday"] = "1D"
    version: int = 1
    description: str = ""
    min_history: int = 0                     # warmup bars needed
    compute_fn: Callable | None = field(default=None, compare=False, repr=False)

    @property
    def fingerprint(self) -> str:
        raw = f"{self.id}|v{self.version}|{self.inputs}|{self.frequency}".encode()
        return hashlib.sha256(raw).hexdigest()[:12]


class FeatureRegistry:
    """Central registry of all features. Features are registered once at import time."""

    def __init__(self):
        self._features: dict[str, Feature] = {}
        self._by_category: dict[str, list[str]] = {}

    def register(self, feature: Feature) -> Feature:
        if feature.id in self._features:
            raise ValueError(f"Feature '{feature.id}' already registered")
        self._features[feature.id] = feature
        self._by_category.setdefault(feature.category, []).append(feature.id)
        return feature

    def get(self, feature_id: str) -> Feature | None:
        return self._features.get(feature_id)

    def list(self, category: str | None = None) -> list[Feature]:
        if category:
            return [self._features[fid] for fid in self._by_category.get(category, [])]
        return list(self._features.values())

    @property
    def count(self) -> int:
        return len(self._features)


# Global singleton
_registry: FeatureRegistry | None = None


def get_registry() -> FeatureRegistry:
    global _registry
    if _registry is None:
        _registry = FeatureRegistry()
    return _registry


def register_feature(feature: Feature) -> Feature:
    return get_registry().register(feature)
