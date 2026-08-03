"""Regime detector interface and state type."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RegimeState:
    regime: str
    confidence: float
    volatility: str
    trend_strength: float
    timestamp: str = ""


class RegimeDetector(ABC):
    @abstractmethod
    def update(self, price: float) -> RegimeState | None:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...
