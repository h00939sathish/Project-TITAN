"""Verification tests for strategy admission semantics (P0 gate).

Gates covered:
- a REJECTED intent does not mutate bridge position/signal state (so the next
  valid same-direction signal can still fire);
- intents stamp the completed BAR's timestamp, not "now";
- stale (non-advancing) bars fail closed at the risk gate;
- a valid crossover produces exactly one intent and reaches the paper adapter.
"""

from datetime import datetime, timedelta, timezone

import pytest

import titan.strategies.registrations  # noqa: F401
from titan._core import (
    ContractType, Instrument, InstrumentId, Money, ReconciliationConfig, RiskConfig, TradeIntent,
)
from titan.execution import PaperConfig, PaperTradingEngine, SimulatedAdapter
from titan.strategies.bridge import StrategyBridge


def _bridge(**kw) -> StrategyBridge:
    params = dict(strategy_id="ma-crossover", strategy_params={"fast": 2, "slow": 3},
                  account_id="test-1", order_size=1)
    params.update(kw)
    return StrategyBridge(**params)


def _engine() -> PaperTradingEngine:
    # generous freshness threshold so crossover intents (stamped with recent
    # bar timestamps) pass; the STALE test intentionally uses a days-old stamp
    risk_config = RiskConfig(
        ["SPY"], Money("50000", "USD"), 1000, 5000, Money("100000", "USD"),
        0.10, Money("5000", "USD"), 10_000_000, 100,
    )
    cfg = PaperConfig(
        risk_config=risk_config, reconciliation_config=ReconciliationConfig(),
        currency="USD", starting_capital="100000", account_id="test-1", state_path="",
    )
    engine = PaperTradingEngine(cfg, SimulatedAdapter())
    engine.start()
    engine.register_instrument(
        Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
    )
    return engine


class TestAdmissionSemantics:
    def test_rejected_intent_does_not_mutate_state(self):
        """A produced-but-not-admitted intent must not suppress the next
        same-direction signal (the P0 admission defect)."""
        bridge = _bridge()
        # Series that crosses fast over slow upward and keeps going up.
        prices = [100, 100, 90, 80, 100, 105, 106, 107]
        dates = [f"2026-08-04T10:{i:02d}:00Z" for i in range(len(prices))]
        intents = []
        for p, d in zip(prices, dates):
            intent = bridge.on_price("SPY", p, bar_date=d)
            if intent:
                intents.append(intent)
        # Without admission, the next same-direction bar must still fire.
        assert len(intents) >= 2, "rejected/not-admitted intents must not suppress later signals"

    def test_admitted_intent_suppresses_duplicate_same_side(self):
        bridge = _bridge()
        prices = [100, 100, 90, 80, 100, 105, 106]
        dates = [f"2026-08-04T11:{i:02d}:00Z" for i in range(len(prices))]
        first = None
        for p, d in zip(prices, dates):
            intent = bridge.on_price("SPY", p, bar_date=d)
            if intent:
                first = intent
                break
        assert first is not None
        bridge.admitted("SPY", first.side)
        # Same side again on a later bar -> suppressed.
        later = bridge.on_price("SPY", 108.0, bar_date="2026-08-04T12:00:00Z")
        assert later is None


class TestBarTimestamps:
    def test_intent_stamps_bar_timestamp_not_now(self):
        bridge = _bridge()
        prices = [100, 100, 90, 80, 100, 105]
        dates = [f"2026-08-04T10:{i:02d}:00Z" for i in range(len(prices))]
        for p, d in zip(prices, dates):
            intent = bridge.on_price("SPY", p, bar_date=d)
            if intent:
                assert intent.market_data_timestamp == d, (
                    f"intent must carry the completed bar's timestamp '{d}', "
                    f"not 'now' (got '{intent.market_data_timestamp}')")
                return
        pytest.fail("expected a crossover intent")

    def test_no_bar_date_falls_back_to_now(self):
        bridge = _bridge()
        intent = bridge.on_price("SPY", 100.0, bar_date=None)
        if intent is None:  # no crossover on a flat series
            prices = [100, 100, 90, 80, 100, 105]
            for p in prices:
                intent = bridge.on_price("SPY", p)
                if intent:
                    break
        assert intent is not None
        assert intent.market_data_timestamp is not None


class TestStaleFailClosed:
    def test_stale_bar_is_rejected_by_freshness_gate(self):
        engine = _engine()
        old_ts = "2026-08-01T10:30:00Z"  # days old
        intent = TradeIntent(
            "test-strat", "test-pkg", "test-1", "SPY", "BUY", "1", "MARKET", "DAY", "1.0",
            old_ts, price="500.0",
        )
        result = engine.submit_intent(intent)
        assert not result.accepted, "stale-bar intent must fail closed at the freshness gate"
        assert "timestamp" in result.rejection_reason.lower()


class TestCrossoverReachesAdapter:
    def test_valid_crossover_single_intent_reaches_adapter(self):
        engine = _engine()
        bridge = _bridge()
        prices = [100, 100, 90, 80, 100, 105]
        # bar timestamps relative to now so the intent passes the freshness gate
        now = datetime.now(timezone.utc)
        dates = [(now - timedelta(seconds=5 * (len(prices) - i))).isoformat()
                 for i in range(len(prices))]
        intents = []
        for p, d in zip(prices, dates):
            intent = bridge.on_price("SPY", p, bar_date=d)
            if intent:
                intents.append(intent)
        assert len(intents) == 1, "a single crossover must produce exactly one intent"

        result = engine.submit_intent(intents[0])
        assert result.accepted, f"intent must be accepted: {result.rejection_reason}"
        assert result.broker_order_id, "accepted intent must reach the paper adapter (order id)"
