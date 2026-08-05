"""Qualified strategy pool — loads only qualified strategies from the research DB.

Combines StrategyBridge instances for each qualified strategy into a single
interface that paper_session.py can drive.

Usage:
    pool = QualifiedStrategyPool("research_data/titan_research.db")
    pool.load(["ma-crossover", "rsi"])          # explicit list
    pool.load_qualified(include_watchlist=True)  # auto from DB
    intents = pool.on_price(instr, price, date)  # list[TradeIntent]
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from titan._core import TradeIntent
from titan.research.db import ResearchDB, DEFAULT_DB_PATH
from titan.strategies.bridge import StrategyBridge
from titan.strategies.ensemble import WeightedEnsemble, StrategyVote
from titan.strategies.manifest import make_manifest
from titan.strategies.registry import get_registry


def _vote_confidence(signal: str | None) -> float:
    return 1.0 if signal == "BUY" else (-1.0 if signal == "SELL" else 0.0)


class QualifiedStrategyPool:
    """Drives multiple qualified StrategyBridge instances from a single price feed.

    Each tick collects intents from all active bridges and runs the ensemble.
    The ensemble decision (BUY/SELL) is returned instead of individual intents.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        default_order_size: int = 1,
        account_id: str = "paper-1",
    ):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._order_size = default_order_size
        self._account_id = account_id
        self._bridges: dict[str, StrategyBridge] = {}
        self._qualified_ids: list[str] = []
        self._ensemble = WeightedEnsemble(buy_threshold=0.3, sell_threshold=-0.3)
        self._last_signals: dict[str, str | None] = {}
        self._instrument: str | None = None
        self._instrument_positions: dict[str, bool] = {}

    def load_qualified(
        self,
        include_watchlist: bool = False,
        instrument: str = "SPY",
    ) -> list[str]:
        """Load strategies from the research DB qualification table.

        Args:
            include_watchlist: Also include WATCHLIST strategies (for research mode).
            instrument: Instrument to trade.

        Returns: List of loaded strategy IDs.
        """
        if not os.path.exists(self._db_path):
            print(f"Qualification DB not found at {self._db_path}")
            return []

        db = ResearchDB(str(self._db_path))
        quals = db.get_qualifications()
        db.close()

        allowed = {"QUALIFIED"}
        if include_watchlist:
            allowed.add("WATCHLIST")

        loaded = []
        for q in quals:
            if q["status"] not in allowed:
                continue
            sid = q["strategy_id"]
            if sid not in get_registry().list_ids():
                continue
            self._add_bridge(sid, q.get("params_json", "{}"))
            loaded.append(sid)

        self._qualified_ids = loaded
        self._instrument = instrument
        return loaded

    def load_explicit(
        self, strategy_ids: Sequence[str], instrument: str = "SPY"
    ) -> list[str]:
        """Load specific strategy IDs (ignores qualification status, for testing)."""
        loaded = []
        for sid in strategy_ids:
            if sid in get_registry().list_ids():
                self._add_bridge(sid, "{}")
                loaded.append(sid)
        self._qualified_ids = loaded
        self._instrument = instrument
        return loaded

    def _add_bridge(self, sid: str, params_json: str) -> None:
        if sid in self._bridges:
            return
        try:
            params = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError:
            params = {}
        # Only pass known strategy params, not qualification metadata
        known = get_registry().get(sid)
        filtered = {k: v for k, v in params.items()
                    if any(p.name == k for p in known.parameter_schema)}
        self._bridges[sid] = StrategyBridge(
            strategy_id=sid,
            strategy_params=filtered if filtered else None,
            account_id=self._account_id,
            order_size=self._order_size,
        )

    def warmup(self, instrument: str, prices: list[float]) -> None:
        for bridge in self._bridges.values():
            bridge.warmup(instrument, prices)

    def set_position(self, instrument: str, has_position: bool) -> None:
        for bridge in self._bridges.values():
            bridge.set_position(instrument, has_position)
        self._instrument_positions[instrument] = has_position

    def on_price(
        self, instrument: str, price: float, bar_date: str | None = None
    ) -> TradeIntent | None:
        """Feed price to all bridges, run ensemble, return single intent or None."""
        signals: dict[str, str | None] = {}
        intents: dict[str, TradeIntent] = {}

        for sid, bridge in self._bridges.items():
            intent = bridge.on_price(instrument, price, bar_date)
            if intent:
                intents[sid] = intent
                signals[sid] = intent.side
            else:
                # Check if bridge had a signal (not just no position change)
                last_side = bridge._last_intent_sides.get(instrument)
                signals[sid] = last_side

        self._last_signals = signals

        # Build ensemble votes
        votes = []
        for sid in self._bridges:
            sig = signals.get(sid)
            confidence = _vote_confidence(sig)
            votes.append(StrategyVote(strategy_id=sid, vote=sig or "HOLD", confidence=confidence))

        if not votes:
            return None

        result = self._ensemble.decide(votes)
        if result.decision == "NO_TRADE":
            return None

        # Pick the first bridge that voted with the ensemble decision
        for sid in intents:
            if (result.decision == "BUY" and intents[sid].side == "BUY") or \
               (result.decision == "SELL" and intents[sid].side == "SELL"):
                intent = intents[sid]
                return intent

        return None

    @property
    def active_count(self) -> int:
        return len(self._bridges)

    @property
    def qualified_ids(self) -> list[str]:
        return list(self._qualified_ids)

    @property
    def last_signals(self) -> dict[str, str | None]:
        return dict(self._last_signals)
