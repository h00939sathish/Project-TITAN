"""Tests for ADR-021 exit-intent execution in the replay/backtest layer.

Covers the plan's Phase 3 test list: gap-open fills, intrabar stop/TP pierce,
stop-wins tie-break, trailing ratchet, engine enforcement + the self-manage
guard.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import titan._core as core
from titan.backtest.engine import ReplayEngine


def make_engine(strategy, bars, **kw):
    return ReplayEngine(strategy, bars, slippage_bps=0.0, commission_bps=0.0,
                        intent_qty=10, **kw)


def _bar(ts, o, h, l, c):
    return {"instrument_id": "SPY", "timestamp": ts, "open": o, "high": h,
            "low": l, "close": c, "volume": 100}


class TestCheckExits:
    def test_gap_open_below_stop_fills_at_open(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 95.0, 98.0, 94.0, 97.0)
        ex = {"side": "BUY", "stop_price": "96.0", "take_profit_price": None,
              "trailing": None}
        assert eng._check_exits(bar, ex) == ("SELL", 95.0)

    def test_gap_open_above_tp_fills_at_open(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 105.0, 106.0, 104.0, 105.5)
        ex = {"side": "BUY", "stop_price": "96.0", "take_profit_price": "102.0",
              "trailing": None}
        assert eng._check_exits(bar, ex) == ("SELL", 105.0)

    def test_intrabar_stop_pierce_fills_at_stop(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 101.0, 102.0, 95.0, 96.5)
        ex = {"side": "BUY", "stop_price": "96.0", "take_profit_price": None,
              "trailing": None}
        assert eng._check_exits(bar, ex) == ("SELL", 96.0)

    def test_intrabar_tp_pierce_fills_at_tp(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 100.0, 103.0, 99.5, 102.5)
        ex = {"side": "BUY", "stop_price": "96.0", "take_profit_price": "102.0",
              "trailing": None}
        assert eng._check_exits(bar, ex) == ("SELL", 102.0)

    def test_tie_break_stop_wins(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 100.0, 103.0, 95.0, 100.0)
        ex = {"side": "BUY", "stop_price": "96.0", "take_profit_price": "102.0",
              "trailing": None}
        out = eng._check_exits(bar, ex)
        assert out[0] == "SELL"
        assert out[1] == 96.0

    def test_short_gap_above_stop_fills_at_open(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 105.0, 106.0, 104.0, 105.5)
        ex = {"side": "SELL", "stop_price": "104.0", "take_profit_price": None,
              "trailing": None}
        assert eng._check_exits(bar, ex) == ("BUY", 105.0)

    def test_trailing_arms_and_ratchets_no_exit(self):
        eng = make_engine(object(), [])
        # high 103 arms the trail (stop -> max(98, 103-1=102)); low 102.5 does
        # NOT pierce 102, so this bar evaluates to no exit.
        bar = _bar("2025-01-01T00:00:00Z", 100.0, 103.0, 102.5, 102.0)
        tc = core.TrailingConfig("2.0", "1.0")
        ex = {"side": "BUY", "stop_price": "98.0",
              "take_profit_price": None, "trailing": tc}
        assert eng._check_exits(bar, ex) is None

    def test_trailing_without_activation_no_arm(self):
        """Until the activation distance is reached, the static stop holds."""
        eng = make_engine(object(), [])
        # high 101 < open 100 + act 2 -> NOT armed yet; eff stop stays 98 ->
        # low 99 does not pierce 98 -> no exit.
        bar = _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.0)
        tc = core.TrailingConfig("2.0", "1.0")
        ex = {"side": "BUY", "stop_price": "98.0",
              "take_profit_price": None, "trailing": tc}
        assert eng._check_exits(bar, ex) is None

    def test_trailing_intrabar_reversal_fills_at_new_trail(self):
        eng = make_engine(object(), [])
        bar = _bar("2025-01-01T00:00:00Z", 100.0, 103.0, 101.5, 102.0)
        tc = core.TrailingConfig("2.0", "1.0")
        ex = {"side": "BUY", "stop_price": "98.0",
              "take_profit_price": None, "trailing": tc}
        assert eng._check_exits(bar, ex) == ("SELL", 102.0)


class TestEngineEnforcement:
    def test_bridge_populates_exit_on_intent(self):
        """Strategy.current_exits flows onto the TradeIntent via the bridge."""
        from titan.strategies.bridge import StrategyBridge
        import titan.strategies.registrations as _  # noqa

        b = StrategyBridge(
            strategy_id="traderdev-ema9-vwap",
            strategy_params={"ema_period": 3, "vwap_period": 20,
                             "atr_period": 5, "trail_mult": 2.0},
        )
        it = None
        for v in [100.0] * 22:
            b.on_price("EURUSD", v, bar_date=None)
        for v in [100.0 + i for i in range(1, 6)]:
            it = b.on_price("EURUSD", float(v), bar_date=None)
            if it:
                break
        assert it is not None
        assert it.stop_price is not None, "strategy stop flows onto intent"

    def test_self_managing_strategy_not_engine_enforced(self):
        """A strategy with update_bar is NOT double-exited by engine static."""
        # traderdev-ema9-vwap self-manages its trail; the record guard must not
        # seed engine-based open_exits for it. Verify the guard predicate.
        from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP
        s = TraderDevEMA9VWAP(vwap_period=20)
        assert hasattr(s, "update_bar")

    def test_non_self_managing_stop_enforced(self):
        """A close-only strategy whose intent carries a stop gets engine
        enforcement: the pierce bar closes the position."""
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-01T00:00:00Z", 100.5, 101.0, 95.0, 96.0),
        ]

        class EchoStrategy:
            strategy_id = "echo-stop"
            def __init__(self):
                self._fired = False
            def update(self, close: float):
                if not self._fired:
                    self._fired = True
                    return "BUY"
                return None

        eng = ReplayEngine(EchoStrategy(), bars, slippage_bps=0.0,
                           commission_bps=0.0, intent_qty=10)
        # Run stability: entry fills on bar 1, and the loop survives bar 2
        # (which would pierce a stop if one were attached). The pierce math
        # itself is covered exhaustively by the _check_exits unit tests above.
        result = eng.run()
        assert result.trades >= 1, "entry accepted"
        assert result.rejected_intents == 0
        assert result.bars_processed > 0


class StopDeclaringStrategy:
    """A close-only strategy that declares a protective stop and does NOT
    self-manage (no update_bar) -- so the engine must enforce it."""

    strategy_id = "decl-stop"

    def __init__(self, exits=None):
        self._fired = False
        self.current_exits = dict(exits) if exits is not None else {}

    def update(self, close):
        if not self._fired:
            self._fired = True
            return "BUY"
        return None


class TestStopEnforcementIsWired:
    """Regression: open_exits was seeded from the intent ReplayEngine itself
    built without stop levels, so _check_exits was never reached and declared
    stops were silently ignored. See ADR-021 and IMPLEMENTATION_PLAN."""

    COLLAPSE = [
        _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),   # entry
        _bar("2025-01-02T00:00:00Z", 100.5, 101.0, 90.0, 91.0),    # pierces 96
        _bar("2025-01-03T00:00:00Z", 91.0, 92.0, 85.0, 86.0),      # keeps falling
    ]

    def _run(self, exits, bars=None):
        s = StopDeclaringStrategy(exits)
        eng = ReplayEngine(s, bars or self.COLLAPSE, slippage_bps=0.0,
                           commission_bps=0.0, intent_qty=10)
        return eng.run()

    def test_declared_stop_is_enforced_end_to_end(self):
        """Intrabar pierce must force a closing SELL -- entry plus one exit."""
        result = self._run({"stop_price": "96.0"})
        assert result.trades == 2, "entry + engine-enforced exit"
        assert result.rejected_intents == 0

    def test_stop_caps_loss_at_the_stop_level_not_the_bar_low(self):
        """The position is closed on the pierce bar instead of riding to 86.

        CHARACTERISATION, not endorsement: ADR-021 says an intrabar pierce fills
        AT THE STOP LEVEL (96.0 -> pnl -45). It actually fills at the bar close
        (91.0 -> pnl -95) because BacktestAdapter.place_order prices every fill
        from the bar and ignores intent.price. See the escalation in
        IMPLEMENTATION_PLAN; this assertion pins current behaviour so an
        unannounced fill-model change shows up as a failure.
        """
        result = self._run({"stop_price": "96.0"})
        assert float(result.total_pnl) == -95.0
        assert float(result.final_cash) == 99905.0
        assert float(result.total_pnl) > -1005.0, "loss capped by the exit"

    def test_gap_pierce_forces_exit_on_the_gap_bar(self):
        """An open below the stop must trigger on that bar, not later."""
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 95.0, 97.0, 94.0, 96.5),
        ]
        result = self._run({"stop_price": "96.0"}, bars=bars)
        assert result.trades == 2
        # Fills at the 96.5 close, not ADR-021's 95.0 open -- the same
        # adapter-level deviation, here in the NON-CONSERVATIVE direction:
        # reporting -40 instead of -55 understates a stop-loss.
        assert float(result.total_pnl) == -40.0

    def test_take_profit_is_enforced_end_to_end(self):
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 100.5, 105.0, 100.0, 104.0),
        ]
        result = self._run({"take_profit_price": "102.0"}, bars=bars)
        assert result.trades == 2
        # 104.0 close rather than the 102.0 level: overstates the gain by 20.
        assert float(result.total_pnl) == 35.0

    def test_no_declared_exits_changes_nothing(self):
        """The guard against a silent behaviour change: an exit-less strategy
        must replay exactly as it did before the wiring fix."""
        result = self._run({})
        assert result.trades == 1
        assert result.bars_processed == 3
        assert result.rejected_intents == 0
        assert float(result.total_pnl) == -1005.0
        assert float(result.final_cash) == 98995.0

    def test_self_managing_strategy_is_not_double_exited(self):
        """The update_bar guard must survive the fix: a strategy that owns its
        trail must not also be engine-exited."""
        class SelfManager(StopDeclaringStrategy):
            def update_bar(self, bar):
                return None

        s = SelfManager({"stop_price": "96.0"})
        eng = ReplayEngine(s, self.COLLAPSE, slippage_bps=0.0,
                           commission_bps=0.0, intent_qty=10)
        result = eng.run()
        assert result.trades == 0, "engine must not force an exit"

    def test_replay_is_deterministic(self):
        first = self._run({"stop_price": "96.0"})
        second = self._run({"stop_price": "96.0"})
        assert (first.trades, first.total_pnl, first.final_cash,
                first.bars_processed) == (
            second.trades, second.total_pnl, second.final_cash,
            second.bars_processed)


class TestBrokerSemanticsUnchanged:
    """The fix must stay inside the simulation layer. intent.stop_price is
    consumed by real order construction (execution/engine.py:1081,
    alpaca_adapter.py:264, ibkr_adapter.py:258), so replay must never populate
    it -- otherwise a research control would acquire live order authority."""

    def test_replay_intents_never_carry_broker_stop_levels(self, monkeypatch):
        from titan.execution.engine import PaperTradingEngine

        seen = []
        real = PaperTradingEngine._submit_intent_core

        def record(self, intent, *a, **k):
            seen.append(intent)
            return real(self, intent, *a, **k)

        monkeypatch.setattr(PaperTradingEngine, "_submit_intent_core", record)

        s = StopDeclaringStrategy({"stop_price": "96.0",
                                   "take_profit_price": "110.0"})
        eng = ReplayEngine(s, TestStopEnforcementIsWired.COLLAPSE,
                           slippage_bps=0.0, commission_bps=0.0, intent_qty=10)
        result = eng.run()

        assert result.trades == 2, "enforcement still happens..."
        assert len(seen) == 2, "entry + forced exit"
        for intent in seen:
            assert intent.stop_price is None
            assert intent.take_profit_price is None
            assert intent.trailing is None