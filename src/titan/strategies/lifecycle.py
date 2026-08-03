"""Strategy lifecycle state machine — monitors health and auto-suspends."""

from dataclasses import dataclass, field
from enum import Enum


class StrategyStatus(Enum):
    CANDIDATE = "CANDIDATE"
    SHADOW = "SHADOW"
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"

    def can_transition_to(self, target: "StrategyStatus") -> bool:
        allowed = {
            StrategyStatus.CANDIDATE: [StrategyStatus.SHADOW],
            StrategyStatus.SHADOW: [StrategyStatus.ACTIVE, StrategyStatus.SUSPENDED, StrategyStatus.RETIRED],
            StrategyStatus.ACTIVE: [StrategyStatus.WATCH, StrategyStatus.SUSPENDED, StrategyStatus.RETIRED],
            StrategyStatus.WATCH: [StrategyStatus.ACTIVE, StrategyStatus.DEGRADED, StrategyStatus.SUSPENDED],
            StrategyStatus.DEGRADED: [StrategyStatus.WATCH, StrategyStatus.SUSPENDED],
            StrategyStatus.SUSPENDED: [StrategyStatus.WATCH, StrategyStatus.RETIRED, StrategyStatus.ACTIVE],
            StrategyStatus.RETIRED: [],
        }
        return target in allowed.get(self, [])


@dataclass
class StrategyHealth:
    strategy_id: str
    status: StrategyStatus = StrategyStatus.CANDIDATE
    trades_count: int = 0
    rolling_sharpe: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float | None = None
    win_rate: float | None = None
    health_score: float | None = None


class LifecycleEngine:
    def __init__(self, min_trades_for_health: int = 50):
        self._strategies: dict[str, StrategyHealth] = {}
        self.min_trades_for_health = min_trades_for_health

    def register(self, strategy_id: str) -> None:
        if strategy_id not in self._strategies:
            self._strategies[strategy_id] = StrategyHealth(strategy_id=strategy_id)

    def transition(self, strategy_id: str, target: StrategyStatus) -> bool:
        h = self._strategies.get(strategy_id)
        if not h:
            return False
        if h.status.can_transition_to(target):
            h.status = target
            return True
        return False

    def update_health(self, strategy_id: str, trades_count: int, sharpe: float | None = None,
                      profit_factor: float | None = None, max_dd: float | None = None,
                      win_rate: float | None = None) -> None:
        h = self._strategies.get(strategy_id)
        if not h:
            return
        h.trades_count = trades_count
        h.rolling_sharpe = sharpe
        h.profit_factor = profit_factor
        h.max_drawdown_pct = max_dd
        h.win_rate = win_rate

        if trades_count < self.min_trades_for_health:
            h.health_score = None
            return

        score = 50.0
        if sharpe is not None:
            score += min(max((sharpe + 1.0) * 15, -30), 30)
        if profit_factor is not None:
            score += min(max((profit_factor - 1.0) * 20, -20), 20)
        if max_dd is not None:
            score -= min(max_dd * 2, 30)
        h.health_score = round(max(0, min(score, 100)), 1)

    def auto_suspend(self, strategy_id: str) -> bool:
        h = self._strategies.get(strategy_id)
        if not h or h.health_score is None:
            return False
        if h.health_score < 30 and h.status in (StrategyStatus.ACTIVE, StrategyStatus.WATCH, StrategyStatus.DEGRADED):
            return self.transition(strategy_id, StrategyStatus.SUSPENDED)
        if h.health_score < 50 and h.status == StrategyStatus.ACTIVE:
            return self.transition(strategy_id, StrategyStatus.WATCH)
        return False

    def get_health(self, strategy_id: str) -> StrategyHealth | None:
        return self._strategies.get(strategy_id)

    def all_statuses(self) -> dict[str, str]:
        return {sid: h.status.value for sid, h in self._strategies.items()}
