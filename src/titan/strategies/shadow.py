"""Shadow deployment — run strategies in read-only mode alongside live."""

from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ShadowTrade:
    strategy_id: str
    instrument_id: str
    side: str
    quantity: str
    price: float
    timestamp: str
    would_have_pnl: float | None = None


class ShadowDeployer:
    """Runs strategies in shadow (no capital) alongside live.

    Tracks what a strategy *would* have done had it been live.
    """

    def __init__(self):
        self._shadow_trades: dict[str, list[ShadowTrade]] = defaultdict(list)

    def record(self, trade: ShadowTrade) -> None:
        self._shadow_trades[trade.strategy_id].append(trade)

    def trades_for(self, strategy_id: str) -> list[ShadowTrade]:
        return list(self._shadow_trades.get(strategy_id, []))

    def compare_to_live(self, strategy_id: str, live_trades: list[ShadowTrade]) -> dict:
        shadow = self._shadow_trades.get(strategy_id, [])
        if not shadow and not live_trades:
            return {}
        shadow_pnl = sum(t.would_have_pnl or 0.0 for t in shadow)
        live_pnl = sum(t.would_have_pnl or 0.0 for t in live_trades)
        return {
            "strategy_id": strategy_id,
            "shadow_trades": len(shadow),
            "live_trades": len(live_trades),
            "shadow_pnl": round(shadow_pnl, 2),
            "live_pnl": round(live_pnl, 2),
            "pnl_delta": round(shadow_pnl - live_pnl, 2),
        }
