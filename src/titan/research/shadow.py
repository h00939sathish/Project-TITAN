"""Shadow deployment — run unqualified strategies alongside the qualified pool.

Never influences execution. Only generates evidence for future promotion.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from titan.backtest.fills import BarConservativeFillModel
from titan.research.db import ResearchDB, DEFAULT_DB_PATH
from titan.strategies.registry import get_registry

# ponytail: global lock fine for single-process, per-strategy locks if concurrent


class ShadowRunner:
    """Runs unqualified strategies in shadow, logs virtual trades to the research DB.

    Each shadow strategy maintains its own position state and simulated P&L.
    Virtual fills use the same BarConservativeFillModel as the live path.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        slippage_bps: float = 0.5,
        commission_bps: float = 1.0,
        session_id: str = "",
    ):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._fill_model = BarConservativeFillModel(slippage_bps, commission_bps)
        self._session_id = session_id
        self._signal_fns: dict[str, Any] = {}
        self._positions: dict[str, bool] = {}  # strategy_id -> in_position
        self._position_cost: dict[str, float] = {}
        self._position_qty: dict[str, int] = {}
        self._strategies: list[dict] = []  # metadata for report

    def _best_params(self, db: ResearchDB, strategy_id: str) -> dict:
        """Look up best params from the latest qualification run."""
        runs = db.get_runs(strategy_id=strategy_id, limit=10)
        for r in runs:
            if r.get("label", "").startswith("qualification_"):
                try:
                    return json.loads(r.get("params_json", "{}"))
                except json.JSONDecodeError:
                    pass
        return {}

    def load_from_db(self, exclude_qualified: bool = True) -> list[str]:
        """Load strategies not yet qualified.

        Args:
            exclude_qualified: Skip QUALIFIED strategies (they run in the main pool).

        Returns: List of loaded strategy IDs.
        """
        if not os.path.exists(self._db_path):
            return []

        db = ResearchDB(str(self._db_path))
        quals = db.get_qualifications()
        loaded = []
        for q in quals:
            if exclude_qualified and q["status"] == "QUALIFIED":
                continue
            sid = q["strategy_id"]
            if sid not in get_registry().list_ids():
                continue
            params = self._best_params(db, sid)
            self.add_strategy(sid, params, q.get("status", "CANDIDATE"))
            loaded.append(sid)
        db.close()
        return loaded

    def load_all_not_qualified(self) -> list[str]:
        """Convenience: load everything that isn't QUALIFIED."""
        return self.load_from_db(exclude_qualified=True)

    def add_strategy(self, strategy_id: str, params: dict | None = None,
                     status: str = "CANDIDATE") -> None:
        reg = get_registry().get(strategy_id)
        self._signal_fns[strategy_id] = reg.factory(params or {})
        self._positions[strategy_id] = False
        self._position_cost[strategy_id] = 0.0
        self._position_qty[strategy_id] = 0
        self._strategies.append({
            "strategy_id": strategy_id,
            "status": status,
            "params": params or {},
        })

    def warmup(self, instrument: str, prices: list[float]) -> None:
        for fn in self._signal_fns.values():
            for p in prices:
                fn({"close": p})

    def on_price(self, instrument: str, price: float,
                 bar_date: str | None = None,
                 bar: dict | None = None) -> list[dict]:
        """Feed price to all shadow strategies. Returns list of shadow events logged."""
        if bar is not None:
            bar = dict(bar)
            bar["date"] = bar_date or bar.get("timestamp", "")
        else:
            bar = {"close": price, "date": bar_date or ""}
        events = []

        for sid, fn in self._signal_fns.items():
            signal = fn(bar)
            in_pos = self._positions[sid]
            event = {
                "strategy_id": sid,
                "instrument": instrument,
                "bar_date": bar_date,
                "price": price,
                "signal": signal,
            }

            if signal == "BUY" and not in_pos:
                fill = self._fill_model.fill(bar, "buy", 1)
                self._positions[sid] = True
                self._position_cost[sid] = fill.fill_cost
                self._position_qty[sid] = fill.fill_quantity
                event["simulated_side"] = "BUY"
                event["simulated_qty"] = fill.fill_quantity
                event["simulated_pnl"] = 0.0
                events.append(event)

            elif signal == "SELL" and in_pos:
                fill = self._fill_model.fill(bar, "sell", self._position_qty[sid])
                pnl = (fill.fill_cost - fill.commission) - self._position_cost[sid]
                self._positions[sid] = False
                self._position_cost[sid] = 0.0
                self._position_qty[sid] = 0
                event["simulated_side"] = "SELL"
                event["simulated_qty"] = fill.fill_quantity
                event["simulated_pnl"] = round(pnl, 2)
                events.append(event)

            else:
                events.append(event)

        self._write_events(events)
        return events

    def _write_events(self, events: list[dict]) -> None:
        db = ResearchDB(str(self._db_path))
        for e in events:
            db.log_shadow_event(
                strategy_id=e["strategy_id"],
                instrument=e["instrument"],
                bar_date=e["bar_date"],
                price=e["price"],
                signal=e["signal"],
                simulated_side=e.get("simulated_side"),
                simulated_qty=e.get("simulated_qty", 0),
                simulated_pnl=e.get("simulated_pnl", 0.0),
                session_id=self._session_id,
            )
        db.close()

    @property
    def active_count(self) -> int:
        return len(self._signal_fns)

    @property
    def strategy_ids(self) -> list[str]:
        return list(self._signal_fns)
