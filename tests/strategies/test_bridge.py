"""Tests for StrategyBridge."""

import pytest

import titan.strategies.registrations  # noqa: F401
from titan.strategies.bridge import StrategyBridge


class TestStrategyBridge:
    def test_ma_crossover_buy_signal(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            account_id="test-1",
            order_size=1,
        )
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 1
        assert intents[0].side == "BUY"
        assert intents[0].instrument_id == "SPY"
        assert intents[0].quantity == "1"

    def test_ma_crossover_sell_signal(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            account_id="test-1",
            order_size=1,
        )
        prices = [100, 100, 90, 80, 100, 120, 125, 120, 115]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
                bridge.admitted("SPY", intent.side)  # admission semantics (P0)
        buy_intents = [i for i in intents if i.side == "BUY"]
        sell_intents = [i for i in intents if i.side == "SELL"]
        assert len(buy_intents) == 1
        assert len(sell_intents) == 1

    def test_no_duplicate_buy(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
        )
        bridge.set_position("SPY", True)
        prices = [100, 100, 90, 80, 100, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert len(intents) == 0

    def test_no_sell_without_position(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
        )
        bridge.set_position("SPY", False)
        prices = [100, 100, 110, 120, 115, 110, 105]
        intents = []
        for p in prices:
            intent = bridge.on_price("SPY", p)
            if intent:
                intents.append(intent)
        assert all(i.side == "BUY" for i in intents)

    def test_unknown_strategy_raises(self):
        with pytest.raises(KeyError, match="Unknown strategy"):
            StrategyBridge(strategy_id="nonexistent")

    def test_default_params(self):
        bridge = StrategyBridge(strategy_id="ma-crossover")
        assert bridge._strategy_id == "ma-crossover"
        assert bridge._account_id == "paper-1"

    def test_multiple_instruments(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
        )
        spy_prices = [100, 100, 90, 80, 100, 105]
        qqq_prices = [200, 200, 180, 160, 200, 210]
        intents = []
        for s, q in zip(spy_prices, qqq_prices):
            i1 = bridge.on_price("SPY", s)
            i2 = bridge.on_price("QQQ", q)
            if i1:
                intents.append(i1)
            if i2:
                intents.append(i2)
        assert len(intents) >= 2

    def test_intent_fields(self):
        bridge = StrategyBridge(
            strategy_id="ma-crossover",
            strategy_params={"fast": 2, "slow": 3},
            account_id="test-1",
            order_size=3,
        )
        prices = [100, 100, 90, 80, 100, 105]
        intent = None
        for p in prices:
            intent = bridge.on_price("SPY", p)
        assert intent is not None
        assert intent.strategy_id == "ma-crossover"
        assert intent.account_id == "test-1"
        assert intent.quantity == "3"
        assert intent.order_type == "MARKET"
        assert intent.time_in_force == "DAY"
        assert intent.price is not None and float(intent.price) > 0


class TestStrategyBridgeWarmup:
    """Tests for warmup and date-aware dedup (uses dual-ma for deterministic signals)."""

    def test_warmup_no_intents(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        assert bridge._has_position.get("SPY") is None

    def test_warmup_indicators_ready(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        # fast MA(2)=102.5, slow MA(3)=95 → signal=BUY, not in pos → intent
        intent = bridge.on_price("SPY", 110)
        assert intent is not None
        assert intent.side == "BUY"

    def test_warmup_long_target_enters_flat_portfolio_once(self):
        bridge = StrategyBridge(
            strategy_id="time-series-momentum",
            strategy_params={"lookback": 2},
        )
        bridge.warmup("SPY", [100.0, 101.0, 102.0])
        bridge.set_position("SPY", False)

        intent = bridge.on_price("SPY", 103.0, bar_date="2026-07-15")

        assert intent is not None
        assert intent.side == "BUY"
        assert bridge.on_price("SPY", 103.0, bar_date="2026-07-15") is None

    def test_current_signal_replaces_warmup_target(self):
        bridge = StrategyBridge(
            strategy_id="time-series-momentum",
            strategy_params={"lookback": 2},
        )
        bridge.warmup("SPY", [100.0, 101.0, 102.0])
        bridge.set_position("SPY", True)

        exit_intent = bridge.on_price("SPY", 90.0, bar_date="2026-07-15")

        assert exit_intent is not None
        assert exit_intent.side == "SELL"
        bridge.admitted("SPY", exit_intent.side)  # admission semantics (P0)
        assert bridge.on_price("SPY", 89.0, bar_date="2026-07-16") is None

    def test_warmup_idempotent(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        bridge.warmup("SPY", [200, 300, 400])
        intent = bridge.on_price("SPY", 110)
        assert intent is not None

    def test_bar_date_dedup(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        intent1 = bridge.on_price("SPY", 110, bar_date="2026-07-15")
        assert intent1 is not None
        bridge.admitted("SPY", intent1.side)  # admission semantics (P0)
        intent2 = bridge.on_price("SPY", 111, bar_date="2026-07-15")
        assert intent2 is None
        intent3 = bridge.on_price("SPY", 112, bar_date="2026-07-16")
        assert intent3 is None  # duplicate side prevention (still BUY)

    def test_bar_date_restart_dedup(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        intent = bridge.on_price("SPY", 110, bar_date="2026-07-14")
        assert intent is not None
        state = bridge.save_state()
        bridge2 = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        bridge2.restore_state(state)
        bridge2.warmup("SPY", prices)
        intent2 = bridge2.on_price("SPY", 110, bar_date="2026-07-14")
        assert intent2 is None
        bridge2._has_position["SPY"] = False
        bridge2._last_intent_sides.pop("SPY", None)
        intent3 = bridge2.on_price("SPY", 111, bar_date="2026-07-15")
        assert intent3 is not None

    def test_duplicate_side_prevention(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        intent1 = bridge.on_price("SPY", 110)
        assert intent1 is not None
        assert intent1.side == "BUY"
        bridge.admitted("SPY", intent1.side)  # admission semantics (P0)
        intent2 = bridge.on_price("SPY", 115)
        assert intent2 is None

    def test_state_round_trip(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        prices = [100, 100, 90, 80, 100, 105]
        bridge.warmup("SPY", prices)
        intent = bridge.on_price("SPY", 110, bar_date="2026-07-14")
        assert intent is not None
        bridge.admitted("SPY", intent.side)  # admission semantics (P0)
        state = bridge.save_state()
        assert "last_bar_dates" in state
        assert state["last_bar_dates"].get("SPY") == "2026-07-14"
        assert "last_intent_sides" in state
        assert state["last_intent_sides"].get("SPY") == "BUY"

    def test_restore_empty_state(self):
        bridge = StrategyBridge(
            strategy_id="dual-ma",
            strategy_params={"fast": 2, "slow": 3},
        )
        bridge.restore_state({})
        assert bridge._last_bar_dates == {}
        assert bridge._last_intent_sides == {}
