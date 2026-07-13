"""Deterministic replay clock — advances by event time."""

from dataclasses import dataclass


@dataclass
class ReplayClock:
    timestamp: str | None = None
    event_index: int = 0

    def advance_to(self, timestamp: str):
        self.timestamp = timestamp
        self.event_index += 1

    @property
    def current_time(self) -> str:
        return self.timestamp or "1970-01-01T00:00:00"
