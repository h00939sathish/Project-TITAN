"""Experiment model — the central object defining a research question."""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Experiment:
    """An immutable research experiment.

    Everything revolves around this object. The question defines what
    we're testing, the dataset and features define the inputs, and the
    target defines what we're predicting. Every experiment MUST begin with
    an economic rationale before execution.
    """

    id: str
    question: str
    economic_rationale: str
    dataset_id: str
    features: tuple[str, ...]
    target: str
    filter_expr: str | None = None       # e.g. "vol_contraction_flag == True AND relative_strength_60d > 0"
    params: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.economic_rationale or len(self.economic_rationale.strip()) < 15:
            raise ValueError(
                f"Experiment {self.id} rejected: Every new experiment must define a clear economic rationale "
                f"rooted in market structure/mechanics before code execution."
            )

    @property
    def fingerprint(self) -> str:
        """Deterministic hash — same experiment = same fingerprint."""
        d = {
            "id": self.id,
            "question": self.question,
            "economic_rationale": self.economic_rationale,
            "dataset_id": self.dataset_id,
            "features": sorted(self.features),
            "target": self.target,
            "filter": self.filter_expr,
            "params": self.params,
        }
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Evidence:
    """Immutable statistical output of an experiment.

    This is what survives from an experiment run — not the raw data,
    not the intermediate calculations, just the statistical findings.
    """

    experiment_id: str
    dataset_id: str

    # Core statistics
    information_coefficient: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    sample_size: int = 0

    # Stability
    stable_bull: bool | None = None
    stable_bear: bool | None = None
    stable_sideways: bool | None = None
    stable_decades: bool | None = None

    # Practicality
    survived_costs: bool | None = None
    lookahead_safe: bool = True
    leakage_free: bool = True

    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)
    fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "dataset_id": self.dataset_id,
            "ic": self.information_coefficient,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "sample_size": self.sample_size,
            "stable_bull": self.stable_bull,
            "stable_bear": self.stable_bear,
            "stable_sideways": self.stable_sideways,
            "stable_decades": self.stable_decades,
            "survived_costs": self.survived_costs,
            "lookahead_safe": self.lookahead_safe,
            "leakage_free": self.leakage_free,
            "computed_at": self.computed_at.isoformat(),
            "fingerprint": self.fingerprint,
        }


@dataclass
class Scorecard:
    """Research Scorecard — records both successful and rejected hypotheses.

    This is the permanent record of every experiment run.
    """

    experiment_id: str
    question: str
    evidence: Evidence | None = None
    checks: dict[str, bool | str] = field(default_factory=dict)
    promoted: bool = False
    notes: str = ""

    def summary(self) -> str:
        lines = [
            f"╔══ EXPERIMENT {self.experiment_id} ═══════════════════════",
            f"║  {self.question}",
            f"║",
        ]
        for check, result in self.checks.items():
            icon = "✅" if result is True else ("❌" if result is False else "⚠️")
            lines.append(f"║  {icon} {check}: {result}")
        if self.evidence:
            e = self.evidence
            lines.extend([
                f"║",
                f"║  IC:          {e.information_coefficient:.4f}" if e.information_coefficient else "║  IC:           N/A",
                f"║  p-value:     {e.p_value:.4f}" if e.p_value else "║  p-value:      N/A",
                f"║  Effect size: {e.effect_size:.4f}" if e.effect_size else "║  Effect size:  N/A",
                f"║  Sample:      {e.sample_size}",
                f"║  Costs:       {'🟢 survived' if e.survived_costs else '🔴 failed'}" if e.survived_costs is not None else "",
            ])
        lines.append(f"║")
        verdict = "🟢 PROMOTED to candidate" if self.promoted else "🔴 REJECTED"
        lines.append(f"║  Verdict: {verdict}")
        if self.notes:
            lines.append(f"║  Notes: {self.notes}")
        lines.append(f"╚═══════════════════════════════════════════")
        return "\n".join(lines)
