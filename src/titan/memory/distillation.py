"""Semantic Rule Distillation Engine for TITAN Trade Memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Sequence

from titan.memory.vector_memory import VectorTradeMemory, TradeMemoryRecord


@dataclass
class RuleCandidate:
    rule_id: str
    rule_name: str
    regime_tag: str
    sample_size: int
    win_rate: float
    avg_pnl: float
    confidence_score: float
    recommendation: str


class RuleDistiller:
    """Distills structured quantitative rule candidates from vector trade memory clusters."""

    def __init__(self, min_sample_size: int = 3, min_win_rate: float = 0.50):
        self.min_sample_size = min_sample_size
        self.min_win_rate = min_win_rate

    def distill_rules(self, memory: VectorTradeMemory) -> list[RuleCandidate]:
        """Cluster trade records by regime and distill rule candidates."""
        records: list[TradeMemoryRecord] = list(memory._records.values())
        if not records:
            return []

        regime_groups: dict[str, list[TradeMemoryRecord]] = defaultdict(list)
        for r in records:
            for tag in r.regime_tags:
                regime_groups[tag].append(r)

        candidates: list[RuleCandidate] = []
        for regime, group in regime_groups.items():
            if len(group) < self.min_sample_size:
                continue

            wins = sum(1 for r in group if r.pnl > 0)
            win_rate = wins / len(group)
            avg_pnl = sum(r.pnl for r in group) / len(group)

            if win_rate >= self.min_win_rate:
                confidence = min(1.0, (len(group) / 10.0) * win_rate)
                rec = "FAVORABLE" if win_rate >= 0.60 else "NEUTRAL"
                candidates.append(
                    RuleCandidate(
                        rule_id=f"rule_{regime.lower()}",
                        rule_name=f"Strategy rule for {regime}",
                        regime_tag=regime,
                        sample_size=len(group),
                        win_rate=round(win_rate, 4),
                        avg_pnl=round(avg_pnl, 2),
                        confidence_score=round(confidence, 4),
                        recommendation=rec,
                    )
                )

        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates
