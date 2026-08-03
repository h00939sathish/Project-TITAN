"""Weighted ensemble — combines strategy votes into a single decision.

Each strategy votes BUY/SELL/HOLD with a confidence score [-1, 1].
Weights are applied and total score is compared to thresholds.
"""

from dataclasses import dataclass, field


@dataclass
class StrategyVote:
    strategy_id: str
    vote: str  # "BUY" | "SELL" | "HOLD"
    confidence: float  # -1 to 1; positive = long bias, negative = short bias
    weight: float = 1.0


@dataclass
class EnsembleResult:
    score: float
    decision: str  # "BUY" | "SELL" | "NO_TRADE"
    votes: list[dict] = field(default_factory=list)
    buy_threshold: float = 0.6
    sell_threshold: float = -0.6


class WeightedEnsemble:
    def __init__(
        self,
        buy_threshold: float = 0.6,
        sell_threshold: float = -0.6,
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def decide(self, votes: list[StrategyVote]) -> EnsembleResult:
        if not votes:
            return EnsembleResult(score=0.0, decision="NO_TRADE")

        total_weight = sum(abs(v.weight) for v in votes) or 1.0
        score = sum(v.confidence * v.weight for v in votes) / total_weight

        if score >= self.buy_threshold:
            decision = "BUY"
        elif score <= self.sell_threshold:
            decision = "SELL"
        else:
            decision = "NO_TRADE"

        return EnsembleResult(
            score=round(score, 4),
            decision=decision,
            votes=[{"id": v.strategy_id, "vote": v.vote, "confidence": v.confidence, "weight": v.weight} for v in votes],
            buy_threshold=self.buy_threshold,
            sell_threshold=self.sell_threshold,
        )
