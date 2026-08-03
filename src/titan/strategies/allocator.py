"""Meta Allocator — tracks per-strategy performance and adapts ensemble weights."""

from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class StrategyRecord:
    strategy_id: str
    total_trades: int = 0
    wins: int = 0
    total_pnl: float = 0.0
    sharpe: float = 0.0
    weight: float = 1.0


class MetaAllocator:
    """Continuously adjusts ensemble weights based on observed performance.

    Higher sharpe / pnl → higher weight.  Weight floor prevents total exclusion.
    """

    def __init__(self, default_weight: float = 1.0, weight_floor: float = 0.2, weight_ceiling: float = 2.0):
        self.default_weight = default_weight
        self.weight_floor = weight_floor
        self.weight_ceiling = weight_ceiling
        self._records: dict[str, StrategyRecord] = {}

    def register(self, strategy_id: str) -> None:
        if strategy_id not in self._records:
            self._records[strategy_id] = StrategyRecord(strategy_id=strategy_id, weight=self.default_weight)

    def record_trade(self, strategy_id: str, pnl: float, side: str) -> None:
        r = self._records.get(strategy_id)
        if not r:
            return
        r.total_trades += 1
        r.total_pnl += pnl
        if pnl > 0:
            r.wins += 1

    def update_sharpe(self, strategy_id: str, sharpe: float) -> None:
        r = self._records.get(strategy_id)
        if r:
            r.sharpe = sharpe

    def rebalance(self) -> dict[str, float]:
        scores = {}
        for sid, r in self._records.items():
            if r.total_trades < 10:
                scores[sid] = self.default_weight
            else:
                win_rate = r.wins / max(r.total_trades, 1)
                score = max(r.sharpe, 0) * 0.6 + win_rate * 2.0 * 0.4
                scores[sid] = max(self.weight_floor, min(score, self.weight_ceiling))

        total = sum(scores.values()) or 1.0
        if total > 0:
            for sid in scores:
                scores[sid] = round(scores[sid] / total * len(scores), 4)

        for sid, w in scores.items():
            if sid in self._records:
                self._records[sid].weight = w
        return scores

    def get_weight(self, strategy_id: str) -> float:
        r = self._records.get(strategy_id)
        return r.weight if r else self.default_weight

    def get_record(self, strategy_id: str) -> StrategyRecord | None:
        return self._records.get(strategy_id)
