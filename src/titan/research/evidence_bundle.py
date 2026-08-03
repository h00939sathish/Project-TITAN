"""Immutable Evidence Bundle Generator for Research Governance."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from titan.research.validators.parameter_stability import OptimizationValidationScorecard


@dataclass(frozen=True)
class EvidenceBundle:
    """Immutable evidence bundle required before any strategy enters WATCHLIST."""

    experiment_id: str
    question: str
    strategy_id: str
    timeframe: str
    universe: tuple[str, ...]
    train_ratio: float
    best_params: dict[str, Any]
    scorecard: dict[str, Any]
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "question": self.question,
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "universe": list(self.universe),
            "train_ratio": self.train_ratio,
            "best_params": self.best_params,
            "scorecard": self.scorecard,
            "created_at": self.created_at or datetime.utcnow().isoformat(),
        }

    def save_to_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def create_evidence_bundle(
    experiment_id: str,
    question: str,
    scorecard: OptimizationValidationScorecard,
    train_ratio: float = 0.60,
) -> EvidenceBundle:
    """Factory creating an EvidenceBundle from an OptimizationValidationScorecard."""
    scorecard_dict = {
        "avg_plateau_stability": round(scorecard.avg_plateau_stability, 4),
        "avg_plateau_coverage_pct": round(scorecard.avg_plateau_coverage * 100, 2),
        "cross_instrument_consistency_pct": round(scorecard.cross_instrument_consistency * 100, 2),
        "walk_forward_passed": scorecard.walk_forward_passed,
        "bootstrap_passed": scorecard.bootstrap_passed,
        "passed_all_checks": scorecard.passed_all_checks,
        "rejection_reasons": list(scorecard.rejection_reasons),
    }

    return EvidenceBundle(
        experiment_id=experiment_id,
        question=question,
        strategy_id=scorecard.strategy_id,
        timeframe=scorecard.timeframe,
        universe=scorecard.universe,
        train_ratio=train_ratio,
        best_params=scorecard.best_params,
        scorecard=scorecard_dict,
        created_at=datetime.utcnow().isoformat(),
    )
