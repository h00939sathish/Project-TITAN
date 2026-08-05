"""Persistent Hypothesis Registry & Classification Schema for Research OS.

Hypothesis is the preregistration contract for a research experiment. It carries
the economic rationale, strategy linkage, data universe, train/test split, and
pre-registered success/failure criteria — everything needed to evaluate a
hypothesis without hindsight bias. Sample-adequacy follows two paths:

- Path A: enough preregistered (expected) trades for the statistical test.
- Path B: a declared alternative evidence standard (e.g. long history with
  walk-forward validation) when the expected trade count is too low.

Production consumers that construct Hypothesis: scripts/validate.py,
scripts/run_pooled_study.py, titan/research/harness.py, multi_harness.py.
Do not change this schema without updating those call sites and
tests/research/test_hypothesis.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Hypothesis:
    """An economically-motivated, preregistered scientific hypothesis."""

    id: str
    title: str
    economic_rationale: str
    strategy_id: str
    instrument: str
    universe: str
    calendar: str
    train_period: str
    test_period: str
    success_criteria: list[str]
    failure_criteria: list[str]
    strategy_params: dict[str, Any] = field(default_factory=dict)
    costs: str = ""
    expected_trade_frequency: str = ""
    sample_adequacy_policy: str = "Path A"  # "Path A" | "Path B"
    path_b_evidence_standard: str = ""
    status: str = "preregistered"  # preregistered, running, qualified, rejected, ...
    preregistered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""

    def __post_init__(self) -> None:
        # Path B requires an explicit evidence standard; Path A does not.
        if self.sample_adequacy_policy == "Path B" and not self.path_b_evidence_standard:
            raise ValueError(
                "Path B hypotheses must declare a path_b_evidence_standard"
            )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Hypothesis":
        """Rebuild a Hypothesis from the dict produced by to_dict()."""
        return cls(**{k: v for k, v in d.items() if k in (
            "id", "title", "economic_rationale", "strategy_id", "strategy_params",
            "instrument", "universe", "calendar", "train_period", "test_period",
            "success_criteria", "failure_criteria", "costs",
            "expected_trade_frequency", "sample_adequacy_policy",
            "path_b_evidence_standard", "status", "preregistered_at", "notes",
        )})

    @property
    def priority_score(self) -> float:
        """Placeholder priority — retained for back-compat with any callers."""
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority_score"] = self.priority_score
        return d


class HypothesisRegistry:
    """Persistent registry linking hypotheses to scientific experiment histories."""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path
        self.hypotheses: dict[str, Hypothesis] = {}

    def register(self, h: Hypothesis) -> None:
        self.hypotheses[h.id] = h
        if self.storage_path:
            self._save()

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {hid: h.to_dict() for hid, h in self.hypotheses.items()}
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")