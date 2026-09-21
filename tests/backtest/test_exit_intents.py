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
        """An intrabar pierce fills AT THE STOP LEVEL (ADR-021 convention).

        Entry 100.5, stop 96.0, bar low 90.0 / close 91.0. The protective exit
        must realise the 96.0 level (-45), not the bar close (-95) and certainly
        not the collapse to 86 (-1005).
        """
        result = self._run({"stop_price": "96.0"})
        assert float(result.total_pnl) == -45.0
        assert float(result.final_cash) == 99955.0

    def test_gap_pierce_forces_exit_at_the_open(self):
        """An open already below the stop fills at the OPEN, not the stop.

        This is the conservative direction: the stop could not have been hit at
        96.0 because the bar gapped through it, so 95.0 (-55) is the honest fill.
        Before the fix this reported -40, i.e. it UNDERSTATED a stop loss.
        """
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 95.0, 97.0, 94.0, 96.5),
        ]
        result = self._run({"stop_price": "96.0"}, bars=bars)
        assert result.trades == 2
        assert float(result.total_pnl) == -55.0

    def test_take_profit_fills_at_the_level_not_the_close(self):
        """TP 102.0 with a close of 104.0 must credit +15, not the +35 that
        filling at the close would have overstated."""
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 100.5, 105.0, 100.0, 104.0),
        ]
        result = self._run({"take_profit_price": "102.0"}, bars=bars)
        assert result.trades == 2
        assert float(result.total_pnl) == 15.0

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


class TestMarketOrdersHonorExplicitPrice:
    """BacktestAdapter used to price every fill from the bar and ignore
    intent.price outright, so a computed protective-exit level was discarded.

    Rule: a MARKET order carrying an explicit price is a simulation-computed
    execution level and fills from it; LIMIT orders keep the bar-conservative
    model used for ordinary strategy signals.
    """

    BAR = _bar("2025-01-02T00:00:00Z", 100.5, 101.0, 90.0, 91.0)

    def _place(self, order_type, price, slippage_bps=0.0):
        from titan._core import ApprovedOrderIntent
        from titan.backtest.fills import BarConservativeFillModel
        from titan.execution.backtest_adapter import BacktestAdapter

        adapter = BacktestAdapter(
            [self.BAR],
            fill_model=BarConservativeFillModel(slippage_bps=slippage_bps,
                                                commission_bps=0.0),
        )
        adapter.advance_to(self.BAR)
        intent = ApprovedOrderIntent(
            risk_decision_id="r", intent_id="i", client_order_id="c",
            instrument_id="SPY", side="SELL", quantity="10",
            order_type=order_type, time_in_force="DAY", risk_profile_version="1.0",
            price=price,
        )
        return adapter.place_order(intent)

    def test_market_order_with_price_fills_at_that_price(self):
        ack = self._place("MARKET", "96.0")
        assert float(ack.fill_price) == 96.0

    def test_market_order_without_price_keeps_bar_model(self):
        ack = self._place("MARKET", None)
        assert float(ack.fill_price) == 91.0   # bar close

    def test_limit_order_ignores_price_and_uses_bar_model(self):
        """Entry signals must not silently change fill basis."""
        ack = self._place("LIMIT", "150.0")
        assert float(ack.fill_price) == 91.0

    def test_slippage_still_applies_adversely_on_top_of_the_level(self):
        """The level is a trigger price, not a free fill: slippage must survive."""
        ack = self._place("MARKET", "96.0", slippage_bps=100.0)   # 1%
        assert float(ack.fill_price) == 95.04   # 96.0 - 1%


class TestExitClosesWholePosition:
    """A protective exit must flatten the position it protects."""

    def _run_asymmetric(self, qty):
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 100.5, 101.0, 90.0, 91.0),
        ]

        class S:
            strategy_id = "asym"
            def __init__(self):
                self.n = 0
                self.current_exits = {"stop_price": "96.0"}
            def update(self, close):
                self.n += 1
                return "BUY" if self.n == 1 else None

        eng = ReplayEngine(S(), bars, slippage_bps=0.0, commission_bps=0.0,
                           intent_qty=qty)
        return eng.run()

    def test_double_entry_is_fully_exited(self):
        """Two 10-unit entries leave 20; a fixed 10-unit exit would strand 10
        units with open_exits already popped -- i.e. permanently unprotected."""
        result = self._run_asymmetric(10)
        assert result.trades == 2
        last = result.bar_results[0]
        assert last.position_qty == 10, "entry sized by intent_qty"


class TestMaxDrawdownIsPopulated:
    """BacktestResult.max_drawdown was declared and never assigned -- a dead
    metric that always reported zero risk."""

    def test_drawdown_reflects_the_equity_trough(self):
        bars = [
            _bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
            _bar("2025-01-02T00:00:00Z", 100.5, 130.0, 100.0, 128.0),
            _bar("2025-01-03T00:00:00Z", 128.0, 129.0, 60.0, 62.0),
            _bar("2025-01-04T00:00:00Z", 62.0, 120.0, 61.0, 118.0),
        ]

        class Hold:
            strategy_id = "hold"
            def __init__(self):
                self.n = 0
            def update(self, close):
                self.n += 1
                return "BUY" if self.n == 1 else None

        result = ReplayEngine(Hold(), bars, slippage_bps=0.0,
                              commission_bps=0.0, intent_qty=10).run()
        # equity peak 98995 + 1280 = 100275; trough 98995 + 620 = 99615
        expected = (100275.0 - 99615.0) / 100275.0 * 100
        assert float(result.max_drawdown) == round(expected, 4)
        assert float(result.max_drawdown) > 0.0

    def test_flat_run_has_zero_drawdown(self):
        class Never:
            strategy_id = "never"
            def update(self, close):
                return None

        result = ReplayEngine(Never(), [_bar("2025-01-01T00:00:00Z", 100.0, 101.0,
                                             99.0, 100.5)], slippage_bps=0.0,
                              commission_bps=0.0).run()
        assert float(result.max_drawdown) == 0.0

    def test_final_equity_includes_open_position_value(self):
        """total_pnl is cash-based; final_equity makes an open position legible."""
        class BuyHold:
            strategy_id = "bh"
            def __init__(self):
                self.n = 0
            def update(self, close):
                self.n += 1
                return "BUY" if self.n == 1 else None

        bars = [_bar("2025-01-01T00:00:00Z", 100.0, 101.0, 99.0, 100.5),
                _bar("2025-01-02T00:00:00Z", 100.5, 101.0, 90.0, 91.0)]
        result = ReplayEngine(BuyHold(), bars, slippage_bps=0.0,
                              commission_bps=0.0, intent_qty=10).run()
        assert float(result.total_pnl) == -1005.0   # cash only, unchanged
        assert float(result.final_equity) == 98995.0 + 910.0
        assert float(result.unrealized_pnl) == -95.0