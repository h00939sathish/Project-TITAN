"""Negative Results Library — maintains a permanent record of every experiment.

This is the single source of truth for what's been tested and what was found.
It prevents rediscovering dead ends.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class NegativeResultEntry:
    experiment_id: str
    question: str
    hypothesis_class: str  # trend, mean_reversion, cross_sectional, etc.
    decision: str          # promote / refine / reject / archive
    confidence: str        # high / medium / low
    ic: float | None
    sample_size: int
    reasons: list[str]
    dataset_id: str
    features: list[str]
    target: str
    failure_type: str = ""     # inconsistent_cross_section, small_sample, cost_negative, ci_crosses_zero, low_ic
    reusable_features: list[str] = field(default_factory=list)
    next_questions: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""


class NegativeResultsLibrary:
    """Persistent store of all experiment outcomes."""

    def __init__(self, path: str | Path = "research/results/library.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, NegativeResultEntry] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for eid, d in data.items():
                self._entries[eid] = NegativeResultEntry(**d)

    def _save(self):
        data = {
            eid: {
                "experiment_id": e.experiment_id,
                "question": e.question,
                "decision": e.decision,
                "confidence": e.confidence,
                "ic": e.ic,
                "sample_size": e.sample_size,
                "reasons": e.reasons,
                "dataset_id": e.dataset_id,
                "features": e.features,
                "target": e.target,
                "timestamp": e.timestamp,
                "notes": e.notes,
            }
            for eid, e in self._entries.items()
        }
        self.path.write_text(json.dumps(data, indent=2))

    def add(self, entry: NegativeResultEntry):
        self._entries[entry.experiment_id] = entry
        self._save()

    def get(self, experiment_id: str) -> NegativeResultEntry | None:
        return self._entries.get(experiment_id)

    def list(self, decision: str | None = None) -> list[NegativeResultEntry]:
        entries = list(self._entries.values())
        if decision:
            entries = [e for e in entries if e.decision == decision]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def summary(self) -> str:
        total = len(self._entries)
        promoted = sum(1 for e in self._entries.values() if e.decision == "promote")
        refined = sum(1 for e in self._entries.values() if e.decision == "refine")
        rejected = sum(1 for e in self._entries.values() if e.decision == "reject")
        archived = sum(1 for e in self._entries.values() if e.decision == "archive")
        return (
            f"Negative Results Library — {total} experiments\n"
            f"  🟢 Promoted: {promoted}\n"
            f"  🟡 Refined:  {refined}\n"
            f"  🔴 Rejected: {rejected}\n"
            f"  ⬜ Archived: {archived}"
        )
