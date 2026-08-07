"""ADR-024 Track 1 — shadow-events path: 1h bars -> BarAggregator -> ShadowRunner
-> shadow_events rows that gates 6/7 (shadow_sufficiency/performance) count.

Exercises the same wiring the FX paper session's _feed_4h_shadow uses, with a
candidate whose signal fires on a simple monotone rise so the simulated BUY is
deterministic.
"""
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import titan.strategies.registrations  # noqa: F401  (populate registry)
from titan.research.db import ResearchDB
from titan.research.shadow import ShadowRunner
from titan.strategies.bar_aggregator import BarAggregator


def _h(hour):
    return datetime(2026, 8, 3, hour, minute=0, tzinfo=timezone.utc)


class TestShadowPath:
    def test_aggregator_to_shadow_events_roundtrip(self):
        """4 aggregated 1h bars -> one 4h bar -> shadow runner logs a row with
        simulated_side set (the exact predicate the promotion gates count)."""
        tmp = Path(tempfile.mkdtemp(prefix="shadow_path_")) / "t.db"
        db = ResearchDB(str(tmp))

        # Warm the runner with a flat series so the strategy is ready, then a
        # rise triggers BUY. The runner's add_strategy uses the registry.
        runner = ShadowRunner(db_path=str(tmp))
        runner.add_strategy("traderdev-ema9-vwap",
                            {"ema_period": 3, "vwap_period": 20,
                             "atr_period": 5, "trail_mult": 2.0})
        for _ in range(40):
            runner.on_price("EURUSD", 1.0000, bar_date=_h(0).isoformat())

        # Feed one 4h bucket (4 x 1h) through the aggregator -> runner.
        agg = BarAggregator(None)
        emitted = []
        for i in range(4):
            emitted += agg.on_1h_bar("EURUSD", _h(i), 1.0000 + i * 0.0001,
                                     1.0010 + i * 0.0001, 0.9995 + i * 0.0001,
                                     1.0005 + i * 0.0001, 100)
        assert len(emitted) == 1
        bar4h = emitted[0]
        events = runner.on_price("EURUSD", bar4h["close"],
                                 bar_date=bar4h["timestamp"], bar=bar4h)
        # one of the returned events must carry a simulated side
        assert any(e.get("simulated_side") is not None for e in events), \
            "expected a simulated fill event"

        # Now assert the DB row the promotion gates actually read.
        rows = db._conn.execute(
            "SELECT strategy_id, simulated_side, simulated_qty FROM shadow_events"
        ).fetchall()
        fills = [r for r in rows if r["simulated_side"] is not None]
        assert fills, "no simulated fill row in shadow_events"
        assert any(r["strategy_id"] == "traderdev-ema9-vwap" for r in fills)
        db.close()

    def test_gate_predicate_counts_simulated_side_rows(self):
        """The exact SQL the promotion gates use must count our rows."""
        tmp = Path(tempfile.mkdtemp(prefix="shadow_path_")) / "t.db"
        db = ResearchDB(str(tmp))
        db.log_shadow_event(strategy_id="s1", instrument="EURUSD",
                            price=1.0, signal="BUY",
                            simulated_side="BUY", simulated_qty=1,
                            simulated_pnl=0.0, session_id="t")
        cnt = db._conn.execute(
            "SELECT COUNT(*) as cnt FROM shadow_events WHERE strategy_id=? "
            "AND simulated_side IS NOT NULL", ("s1",)).fetchone()["cnt"]
        assert cnt == 1
        db.close()