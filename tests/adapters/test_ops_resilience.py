"""Operational resilience tests for PaperTradingEngine.

Covers the Stage-2 operational suite at the unit level with a scripted fake
adapter: restart reconstruction, order bursts (no duplicates/deadlocks),
partial-fill accounting, broker timeouts (no phantom drift, fail-closed),
and external cancellation detection.
"""

import io
import json
import tempfile
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fixtures.session_init import initialize_fresh

from titan._core import (
    BrokerPosition,
    ContractType,
    EventEnvelope,
    EventStore,
    Instrument,
    InstrumentId,
    KillSwitchState,
    Money,
    OrderState,
    OrderStateMachine,
    ReconciliationConfig,
    ReconciliationDriftSeverity,
    RiskConfig,
    TradeIntent,
    TradingState,
)
from titan.execution import (
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    PaperConfig,
    PaperTradingEngine,
)
from titan.execution._broker_adapter import BrokerAdapter
from titan.execution._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    Session,
)
from titan.operations.logging import StructuredLogger, LogSeverity

pytestmark = pytest.mark.usefixtures("sign_uncertified_intents")


def _config(state_path: str = "") -> PaperConfig:
    risk_config = RiskConfig(
        ["AAPL", "MSFT"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )
    return PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="test-1",
        state_path=state_path,
    )


def _make_intent(instrument="AAPL", side="BUY", quantity="100", client_id=None) -> TradeIntent:
    return TradeIntent(
        "test-strat", "test-pkg", "test-1",
        instrument, side, quantity, "MARKET", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        price="150.0",
    certificate_ref="test-cert",
    )


class FakeAdapter(BrokerAdapter):
    """Scripted adapter: place_order behavior + tick status map + failure toggles."""

    def __init__(self):
        self.placed: list[TradeIntent] = []
        self.cancelled: list[BrokerOrderId] = []
        self.tick_status: dict[str, BrokerOrderStatus] = {}
        self.ack_override: BrokerOrderAcknowledgement | None = None
        self.timeout_positions = False
        self.timeout_holdings = False
        self.broker_positions: list[BrokerPosition] = []
        self.broker_cash = Money("100000", "USD")
        self.connected = True

    def authenticate(self) -> Session:
        return Session(
            session_id=str(uuid.uuid4()),
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(
            connected=self.connected,
            session_state=AdapterSessionState.CONNECTED,
            degradation=[],
        )

    def place_order(self, intent) -> BrokerOrderAcknowledgement:
        self.placed.append(intent)
        if self.ack_override is not None:
            return self.ack_override
        return BrokerOrderAcknowledgement(
            accepted=True,
            broker_order_id=BrokerOrderId(id=f"b-{len(self.placed)}"),
            fill_quantity=str(int(intent.quantity)),
            fill_price="150.0",
            order_status="Filled",
        )

    def tick(self, order_id: str) -> BrokerOrderStatus | None:
        return self.tick_status.get(order_id)

    def cancel(self, order_id: BrokerOrderId):
        self.cancelled.append(order_id)
        from titan.execution._broker_types import CancellationAcknowledgement
        return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        if self.timeout_positions:
            raise RuntimeError("simulated positions timeout")
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=list(self.broker_positions),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        if self.timeout_holdings:
            raise RuntimeError("simulated holdings timeout")
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=self.broker_cash,
            portfolio_value=self.broker_cash,
            buying_power=self.broker_cash,
            equity=self.broker_cash,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def order_status(self, order_id: str) -> BrokerOrderStatus | None:
        return self.tick_status.get(order_id)


def _status(order_id, status="Filled", filled="100", price="150.0", instrument="AAPL",
            side="BUY", price_is_cumulative_avg=False):
    kwargs = {}
    if price_is_cumulative_avg:
        kwargs["price_is_cumulative_avg"] = True
    return BrokerOrderStatus(
        order_id=BrokerOrderId(id=order_id),
        instrument_id=instrument,
        side=side,
        quantity="100",
        filled_quantity=filled,
        price=price,
        status=status,
        created_at="",
        updated_at=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


def _ops_feed():
    from titan.data.feed_health import FeedHealthVerdict
    from datetime import datetime, timezone
    return lambda: FeedHealthVerdict(True, "", {}, datetime.now(timezone.utc).isoformat())


def _ops_auth(corr):
    from datetime import datetime, timedelta, timezone
    from titan.risk.release_authorization import (
        ReleaseApproval, ReleaseAuthorization, new_nonce)
    now = datetime.now(timezone.utc).isoformat()
    return ReleaseAuthorization(
        correlation_id=corr or "ks-test", assessment="a", remediation="r",
        approvers=[ReleaseApproval("alice", now), ReleaseApproval("bob", now)],
        issued_at=now, expiry=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        nonce=new_nonce("t"))


def _engine(adapter, state_path=""):
    logger = StructuredLogger(min_severity=LogSeverity.INFO, output=io.StringIO())
    engine = PaperTradingEngine(_config(state_path), adapter, logger=logger, feed_health=_ops_feed())
    for sym in ("AAPL", "MSFT"):
        engine.register_instrument(
            Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
    return engine


# ── 1. Restart mid-session → positions and orders reconstructed ──────────────

def test_restart_reconstruction_positions_and_orders():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        adapter = FakeAdapter()
        engine = _engine(adapter, state_path)
        initialize_fresh(engine)
        engine.start(sync_from_broker=False)
        result = engine.submit_intent(_make_intent())
        assert result.accepted
        # Simulate a restart: fresh engine on the same state path + same broker truth.
        adapter2 = FakeAdapter()
        adapter2.broker_positions = [BrokerPosition("AAPL", "BUY", 100)]
        adapter2.broker_cash = Money("85000", "USD")
        engine2 = _engine(adapter2, state_path)
        try:
            engine2.start(sync_from_broker=True)
            pos = engine2.portfolio.get_position("AAPL")
            assert pos is not None and pos.quantity == 100
            assert float(engine2.portfolio.get_cash_balance().amount) == 85000.0
            # The submitted order's state machine was persisted and restored.
            assert len(engine2.order_states) >= 1
        finally:
            engine.stop()
            engine2.stop()


# ── 2. 20 simultaneous orders → no duplicates, no deadlock ───────────────────

def test_burst_20_orders_no_duplicates_no_deadlock():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    results = []
    rejected_idx = []
    for i in range(20):
        instr = "AAPL" if i % 2 == 0 else "MSFT"
        result = engine.submit_intent(_make_intent(instrument=instr, quantity="1"))
        if result.accepted:
            results.append(result)
        else:
            # Rate limiter (10 intents/sec rolling window) must reject cleanly.
            assert "Rate limit" in result.rejection_reason, result.rejection_reason
            rejected_idx.append(i)
    assert len(results) >= 10  # limiter admits 10 per rolling second
    # Wait out the window; breaker must recover and admit the throttled rest.
    time.sleep(1.1)
    for i in rejected_idx:
        instr = "AAPL" if i % 2 == 0 else "MSFT"
        result = engine.submit_intent(_make_intent(instrument=instr, quantity="1"))
        assert result.accepted, f"retry order {i} rejected: {result.rejection_reason}"
        results.append(result)
    # All 20 placed exactly once, no duplicate broker ids, engine responsive.
    assert len(adapter.placed) == 20
    assert len({p.client_order_id for p in adapter.placed}) == 20
    st = engine.status()
    assert st.kill_switch == KillSwitchState.Armed or st.kill_switch == KillSwitchState.Released
    # Portfolio holds 10 AAPL + 10 MSFT
    aapl = engine.portfolio.get_position("AAPL")
    msft = engine.portfolio.get_position("MSFT")
    assert aapl is not None and aapl.quantity == 10
    assert msft is not None and msft.quantity == 10
    engine.stop()


# ── 3. Partial fills → position accounting stays correct ────────────────────

def test_partial_fill_accounting():
    adapter = FakeAdapter()
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-1"),
        fill_quantity="60",           # partial: 60 of 100 filled synchronously
        fill_price="150.0",
        order_status="PartiallyFilled",
    )
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    result = engine.submit_intent(_make_intent())
    assert result.accepted
    assert len(result.fills) == 1 and result.fills[0].quantity == "60"
    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 60
    # Remaining 40 arrive via the poll loop (polled by CLIENT order id).
    client_id = next(iter(engine.order_states))
    adapter.tick_status[client_id] = _status("b-1", status="Filled", filled="100", price="150.5")
    engine.poll_fills()
    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 100
    assert float(pos.cost_basis.amount) == pytest.approx((60 * 150.0 + 40 * 150.5) / 100, abs=0.01)
    engine.stop()


def test_working_partial_fill_booked_before_terminal():
    """A partial reported while the order is still working must reach the
    portfolio on that poll — not only when the order reaches Filled."""
    adapter = FakeAdapter()
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-part"),
        fill_quantity=None,
        fill_price=None,
        order_status="Submitted",       # broker accepted; nothing filled yet
    )
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    result = engine.submit_intent(_make_intent())
    assert result.accepted
    assert result.fills == []
    assert engine.portfolio.get_position("AAPL") is None  # nothing phantom

    client_id = next(iter(engine.order_states))
    # Broker truth: 40 of 100 filled, order still working.
    adapter.tick_status[client_id] = _status(
        "b-part", status="partially_filled", filled="40", price="150.0")
    engine.poll_fills()

    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 40
    assert engine.order_states[client_id].current == OrderState.PartiallyFilled

    # Re-polling the same cumulative quantity must not double-book.
    engine.poll_fills()
    assert engine.portfolio.get_position("AAPL").quantity == 40

    # Remaining 60 fill at 150.5 -> exactly-once terminal booking.
    adapter.tick_status[client_id] = _status(
        "b-part", status="Filled", filled="100", price="150.5")
    engine.poll_fills()
    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 100
    assert engine.order_states[client_id].current == OrderState.Filled
    assert float(pos.cost_basis.amount) == pytest.approx(
        (40 * 150.0 + 60 * 150.5) / 100, abs=0.01)
    engine.stop()


def test_reconcile_agrees_with_working_partial():
    """Reconciliation must compare against broker truth that includes a
    working partial, instead of reporting phantom drift and halting."""
    adapter = FakeAdapter()
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-part2"),
        fill_quantity=None,
        fill_price=None,
        order_status="Submitted",
    )
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    assert engine.submit_intent(_make_intent()).accepted

    client_id = next(iter(engine.order_states))
    adapter.tick_status[client_id] = _status(
        "b-part2", status="partially_filled", filled="40", price="150.0")
    engine.poll_fills()

    adapter.broker_positions = [BrokerPosition("AAPL", "BUY", 40)]
    adapter.broker_cash = Money("94000", "USD")   # 100000 - 40 * 150
    result = engine.reconcile()

    assert result.severity == ReconciliationDriftSeverity.InSync
    assert not engine.status().kill_switch.is_triggered()
    engine.stop()


# ── 4. Broker timeout → no phantom positions/cash drift ─────────────────────

def test_holdings_timeout_no_phantom_cash_drift():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.submit_intent(_make_intent())  # engine long AAPL 100 @150
    adapter.broker_positions = [BrokerPosition("AAPL", "BUY", 100)]  # broker agrees
    adapter.timeout_holdings = True       # broker cash unavailable now
    result = engine.reconcile()
    # Cash verification is skipped — no phantom 100% cash drift, no kill switch.
    assert result.severity != ReconciliationDriftSeverity.Critical
    st = engine.status()
    assert not st.kill_switch.is_triggered()
    engine.stop()


def test_positions_timeout_fail_closed():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.submit_intent(_make_intent())
    adapter.timeout_positions = True
    result = engine.reconcile()
    st = engine.status()
    assert st.kill_switch.is_triggered()  # cannot verify position truth → halt
    engine.stop()


def test_positions_timeout_flat_portfolio_fail_closed():
    """A flat local portfolio must NOT reconcile InSync against an empty set
    when broker positions are unverifiable — empty is indistinguishable from a
    flat broker account, so unavailability itself fails closed (ADR-019)."""
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    adapter.timeout_positions = True
    result = engine.reconcile()
    assert result.severity == ReconciliationDriftSeverity.Critical
    st = engine.status()
    assert st.kill_switch.is_triggered()  # cannot verify position truth → halt
    engine.stop()


# ── 5. Release gate refuses when broker truth is unavailable ─────────────────

def test_release_refused_when_positions_unavailable():
    """Release requires reconciliation; with broker positions unverifiable the
    predicate is unsatisfied and the release must refuse (ADR-019), even with a
    flat portfolio and an otherwise-valid authorization."""
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.trigger_kill_switch()
    adapter.timeout_positions = True
    with pytest.raises(RuntimeError, match="broker_truth_unavailable"):
        engine.release_kill_switch(_ops_auth(corr=engine._kill_correlation))
    assert engine.risk_gate.kill_switch.blocks_routing()
    engine.stop()


def test_release_refused_when_cash_unavailable():
    """Broker cash unavailability is skipped on the periodic path by design,
    but the release gate must refuse: reconciliation that substitutes local
    cash is self-comparison, not verification."""
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.trigger_kill_switch()
    adapter.timeout_holdings = True
    with pytest.raises(RuntimeError, match="broker_truth_unavailable"):
        engine.release_kill_switch(_ops_auth(corr=engine._kill_correlation))
    assert engine.risk_gate.kill_switch.blocks_routing()
    engine.stop()


# ── 6. Kill switch survives restart (fail-closed recovery) ───────────────────

def test_kill_switch_survives_restart():
    """P1 fix: a killed engine must restart in Triggered/Halted, never silently
    resume trading. Uses load_or_default (fail-closed) on the same event store."""
    with tempfile.TemporaryDirectory() as td:
        state_path = str(Path(td) / "state.json")
        adapter = FakeAdapter()
        engine = _engine(adapter, state_path=state_path)
        initialize_fresh(engine)
        engine.start(sync_from_broker=False)
        engine.trigger_kill_switch()   # persists RiskStateSnapshot (Triggered)
        engine.stop()

        # Simulated restart: fresh engine over the same store.
        adapter2 = FakeAdapter()
        engine2 = _engine(adapter2, state_path=state_path)
        engine2.start(sync_from_broker=False)
        st = engine2.status()
        assert st.kill_switch.is_triggered(), (
            "killed engine restarted in a trading state — fail-open recovery"
        )
        # Routing must be blocked on the restarted engine.
        result = engine2.submit_intent(_make_intent())
        assert not result.accepted
        engine2.stop()


def test_fresh_engine_starts_fail_closed_until_explicit_init():
    """Strict recovery: a fresh engine with no prior risk state starts
    Triggered/Halted (fail closed) and becomes Armed/Active only after the
    explicit, audited initialize_new_session command - never implicitly."""
    adapter = FakeAdapter()
    engine = PaperTradingEngine(_config(""), adapter)
    engine.register_instrument(
        Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
    )
    engine.start(sync_from_broker=False)
    st = engine.status()
    assert st.kill_switch.is_triggered()            # fail-closed startup
    assert not st.trading_state.accepts_intents()   # Halted
    initialize_fresh(engine)                        # explicit operator-controlled init
    assert not engine.risk_gate.kill_switch.blocks_routing()
    assert engine.risk_gate.trading_state == TradingState.Active
    engine.stop()


# ── 5. External cancellation detected via poll loop ─────────────────────────

def test_external_cancel_detected():
    adapter = FakeAdapter()
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-9"),
        fill_quantity=None,
        fill_price=None,
        order_status="Submitted",       # order left working at the broker
    )
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    result = engine.submit_intent(_make_intent())
    assert result.accepted
    assert len(result.fills) == 0
    assert engine.portfolio.get_position("AAPL") is None  # nothing phantom
    # Broker later reports the order cancelled (e.g. TWS UI cancel).
    client_id = next(iter(engine.order_states))
    adapter.tick_status[client_id] = _status("b-9", status="Cancelled", filled="0")
    engine.poll_fills()
    # Order transitioned to a dead state; still no phantom position.
    sm = engine.order_states.get(client_id)
    assert sm is not None and sm.current in (OrderState.Rejected, OrderState.Cancelled)
    assert engine.portfolio.get_position("AAPL") is None
    engine.stop()


# ── 7. Kill-switch release cycle ────────────────────────────────────────────

def test_kill_switch_release_cycle():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.submit_intent(_make_intent())          # engine long AAPL 100 @150
    adapter.broker_positions = [BrokerPosition("AAPL", "BUY", 100)]  # broker agrees
    adapter.broker_cash = Money("85000", "USD")   # broker cash reflects the fill too
    # Simulate an operational halt: positions unavailable -> fail-closed trigger.
    adapter.timeout_positions = True
    engine.reconcile()
    assert engine.status().kill_switch.is_triggered()
    assert engine.status().kill_switch.blocks_routing()
    # Broker recovers; the release path reconciles clean and resumes.
    adapter.timeout_positions = False
    engine.release_kill_switch(_ops_auth(corr=engine._kill_correlation))
    st = engine.status()
    assert not st.kill_switch.is_triggered()
    assert not st.kill_switch.blocks_routing()
    assert st.trading_state == TradingState.Active
    engine.stop()


def test_kill_switch_release_refused_on_real_drift():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    engine.submit_intent(_make_intent())          # engine long AAPL 100
    # Broker reports FLAT while the engine holds 100 -> genuine drift.
    adapter.broker_positions = []
    engine.reconcile()
    assert engine.status().kill_switch.is_triggered()
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="Cannot release"):
        engine.release_kill_switch(_ops_auth(corr=engine._kill_correlation))
    engine.stop()

# ── 6. Working order is never rejected/cancelled locally ────────────────────

def test_working_order_stays_pending():
    adapter = FakeAdapter()
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-10"),
        fill_quantity=None,
        fill_price=None,
        order_status="Submitted",
    )
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    result = engine.submit_intent(_make_intent())
    assert result.accepted
    assert adapter.cancelled == []       # NOT cancelled locally
    # Later the broker fills it → poll absorbs the fill.
    client_id = next(iter(engine.order_states))
    adapter.tick_status[client_id] = _status("b-10", status="Filled", filled="100", price="149.0")
    engine.poll_fills()
    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 100
    engine.stop()


# ── 7. Broker-reported expiry is terminal and is not a rejection ────────────

def _acknowledged_order(engine, adapter, fill_quantity=None):
    """Submit an order the broker accepts with no (or a partial) fill."""
    adapter.ack_override = BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id="b-exp"),
        fill_quantity=fill_quantity,
        fill_price="150.0" if fill_quantity else None,
        order_status="PartiallyFilled" if fill_quantity else "Acknowledged",
    )
    result = engine.submit_intent(_make_intent())
    assert result.accepted
    return next(iter(engine.order_states))


def _tracked_polls(adapter):
    """Wrap adapter.tick so the test can count how often an order is polled."""
    calls = []
    tick = adapter.tick

    def counting(order_id):
        calls.append(order_id)
        return tick(order_id)

    adapter.tick = counting
    return calls


def _last_transition(engine, client_id):
    events = [json.loads(e.payload)
              for e in engine._event_store.replay_by_type("OrderTransition")]
    return [e for e in events if e["order_id"] == client_id][-1]


def test_expired_working_order_drains_from_polling():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter)
    assert engine.order_states[client_id].current == OrderState.Acknowledged

    adapter.tick_status[client_id] = _status("b-exp", status="Expired", filled="0")
    polls = _tracked_polls(adapter)

    engine.poll_fills()

    assert engine.order_states[client_id].current == OrderState.Expired
    assert client_id not in engine._order_metadata
    assert polls == [client_id]
    # A terminal order must not be polled again, however many polls run.
    engine.poll_fills()
    engine.poll_fills()
    assert polls == [client_id]
    engine.stop()


def test_expired_with_partial_fill_preserves_position():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter, fill_quantity="60")
    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 60

    # The broker expires the DAY order with the same cumulative fill.
    adapter.tick_status[client_id] = _status(
        "b-exp", status="Expired", filled="60", price="150.0")
    engine.poll_fills()

    pos = engine.portfolio.get_position("AAPL")
    assert pos is not None and pos.quantity == 60
    assert engine.order_states[client_id].current == OrderState.Expired
    assert client_id not in engine._order_metadata
    engine.stop()


def test_expired_transition_persists_as_expired():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter)

    adapter.tick_status[client_id] = _status("b-exp", status="Expired", filled="0")
    engine.poll_fills()

    transition = _last_transition(engine, client_id)
    assert transition["to_state"] == "Expired"
    assert transition["reason"] == "broker_expired"
    engine.stop()


def test_done_for_day_expires_the_order():
    # Alpaca ends a DAY order with "done_for_day", which canonicalizes to Expired.
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter)

    adapter.tick_status[client_id] = _status(
        "b-exp", status="done_for_day", filled="0")
    engine.poll_fills()

    assert engine.order_states[client_id].current == OrderState.Expired
    assert _last_transition(engine, client_id)["to_state"] == "Expired"
    assert client_id not in engine._order_metadata
    engine.stop()


def test_expired_order_is_not_resurrected_on_restart():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        adapter = FakeAdapter()
        engine = _engine(adapter, state_path)
        initialize_fresh(engine)
        engine.start(sync_from_broker=False)
        client_id = _acknowledged_order(engine, adapter)
        adapter.tick_status[client_id] = _status("b-exp", status="Expired", filled="0")
        engine.poll_fills()
        engine.stop()

        adapter2 = FakeAdapter()
        engine2 = _engine(adapter2, state_path)
        engine2.start(sync_from_broker=False)
        try:
            # Replay restores the terminal state, and polling never picks it up.
            # (Startup reconstruction rebuilds metadata for every historical
            # submit, terminal orders included; that structure is not the
            # open-order contract — poll_fills is.)
            assert engine2.order_states[client_id].current == OrderState.Expired
            polls = _tracked_polls(adapter2)
            engine2.poll_fills()
            assert engine2.order_states[client_id].current == OrderState.Expired
            assert polls == []
            assert adapter2.placed == []
        finally:
            engine2.stop()


# ── Fill event vocabulary: partial vs complete ──────────────────────────────

def _fill_events(engine, message_type):
    return [json.loads(e.payload)
            for e in engine._event_store.replay_by_type(message_type)]


def test_partial_ack_emits_order_partially_filled():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter, fill_quantity="60")

    partials = _fill_events(engine, "OrderPartiallyFilled")
    assert [p["filled_quantity"] for p in partials] == [60]
    assert partials[0]["client_order_id"] == client_id
    assert _fill_events(engine, "OrderFilled") == []
    engine.stop()


def test_final_delta_emits_order_filled():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    client_id = _acknowledged_order(engine, adapter, fill_quantity="60")

    adapter.tick_status[client_id] = _status(
        "b-exp", status="Filled", filled="100", price="150.5")
    engine.poll_fills()

    assert engine.order_states[client_id].current == OrderState.Filled
    assert [p["filled_quantity"]
            for p in _fill_events(engine, "OrderPartiallyFilled")] == [60]
    assert [f["filled_quantity"] for f in _fill_events(engine, "OrderFilled")] == [40]
    engine.stop()


def test_complete_ack_emits_only_order_filled():
    adapter = FakeAdapter()
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    assert engine.submit_intent(_make_intent()).accepted

    assert [f["filled_quantity"] for f in _fill_events(engine, "OrderFilled")] == [100]
    assert _fill_events(engine, "OrderPartiallyFilled") == []
    engine.stop()


def test_restart_rebuilds_cumulative_filled_quantity():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        adapter = FakeAdapter()
        engine = _engine(adapter, state_path)
        initialize_fresh(engine)
        engine.start(sync_from_broker=False)
        client_id = _acknowledged_order(engine, adapter, fill_quantity="40")
        adapter.tick_status[client_id] = _status(
            "b-exp", status="PartiallyFilled", filled="70", price="150.5")
        engine.poll_fills()
        assert engine._order_filled_quantity[client_id] == 70
        engine.stop()

        adapter2 = FakeAdapter()
        engine2 = _engine(adapter2, state_path)
        engine2.start(sync_from_broker=False)
        try:
            assert engine2._order_filled_quantity[client_id] == 70
            adapter2.tick_status[client_id] = _status(
                "b-exp", status="Filled", filled="100", price="150.5")
            engine2.poll_fills()
            pos = engine2.portfolio.get_position("AAPL")
            assert pos is not None and pos.quantity == 100
        finally:
            engine2.stop()


def test_legacy_order_filled_deltas_accumulate_on_replay():
    # Logs written before the vocabulary split contain one OrderFilled row per
    # applied delta. Replay must sum them, not keep the last one.
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        db_path = state_path.replace(".json", ".db")
        store = EventStore(db_path)
        for delta in (30, 40):
            store.append(EventEnvelope(
                "OrderFilled", "Execution", "legacy-1", "test_python",
                json.dumps({
                    "client_order_id": "legacy-1",
                    "instrument_id": "AAPL",
                    "side": "BUY",
                    "filled_quantity": delta,
                    "fill_price": "150.0",
                }),
            ))
        store.close()

        engine = _engine(FakeAdapter(), state_path)
        engine.start(sync_from_broker=False)
        try:
            assert engine._order_filled_quantity["legacy-1"] == 70
        finally:
            engine.stop()


# ── Broker cumulative-average price -> incremental delta price ──────────────

def _cumulative_ack(order_id, quantity, price):
    return BrokerOrderAcknowledgement(
        accepted=True,
        broker_order_id=BrokerOrderId(id=order_id),
        fill_quantity=quantity,
        fill_price=price,
        order_status="PartiallyFilled",
        fill_price_is_cumulative_avg=True,
    )


def _fill_payloads(engine):
    return (_fill_events(engine, "OrderPartiallyFilled")
            + _fill_events(engine, "OrderFilled"))


def test_cumulative_avg_second_fill_derives_incremental_price():
    adapter = FakeAdapter()
    adapter.ack_override = _cumulative_ack("b-cum", "60", "150.0")
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    try:
        assert engine.submit_intent(_make_intent()).accepted
        client_id = next(iter(engine.order_states))

        adapter.tick_status[client_id] = _status(
            "b-cum", status="Filled", filled="100", price="156.0",
            price_is_cumulative_avg=True)
        engine.poll_fills()

        pos = engine.portfolio.get_position("AAPL")
        assert pos is not None and pos.quantity == 100
        # 60 @ 150 + 40 @ 165 == 100 @ 156; booking the 40 at 156 would
        # give 152.4 and understate cost basis by 3.6/share.
        assert float(pos.cost_basis.amount) == pytest.approx(156.0, abs=1e-9)

        fills = _fill_payloads(engine)
        assert [f["filled_quantity"] for f in fills] == [60, 40]
        assert float(fills[0]["fill_price"]) == pytest.approx(150.0, abs=1e-9)
        assert float(fills[1]["fill_price"]) == pytest.approx(165.0, abs=1e-9)
        assert float(engine._order_filled_notional[client_id]) == pytest.approx(
            15600.0, abs=1e-6)
    finally:
        engine.stop()


def test_cumulative_avg_three_polls_reconverge_to_broker_vwap():
    adapter = FakeAdapter()
    adapter.ack_override = _cumulative_ack("b-cum3", "40", "150.0")
    engine = _engine(adapter)
    initialize_fresh(engine)
    engine.start(sync_from_broker=False)
    try:
        assert engine.submit_intent(_make_intent()).accepted
        client_id = next(iter(engine.order_states))

        adapter.tick_status[client_id] = _status(
            "b-cum3", status="PartiallyFilled", filled="70", price="152.0",
            price_is_cumulative_avg=True)
        engine.poll_fills()
        adapter.tick_status[client_id] = _status(
            "b-cum3", status="Filled", filled="100", price="155.0",
            price_is_cumulative_avg=True)
        engine.poll_fills()

        pos = engine.portfolio.get_position("AAPL")
        assert pos is not None and pos.quantity == 100
        assert float(pos.cost_basis.amount) == pytest.approx(155.0, abs=1e-9)

        fills = _fill_payloads(engine)
        assert [f["filled_quantity"] for f in fills] == [40, 30, 30]
        prices = [Decimal(str(f["fill_price"])) for f in fills]
        assert prices[0] == Decimal("150.0")
        assert abs(prices[1] - Decimal("4640") / Decimal("30")) < Decimal("1e-20")
        assert abs(prices[2] - Decimal("162")) < Decimal("1e-20")
    finally:
        engine.stop()


def test_cumulative_avg_restart_preserves_incremental_derivation():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        adapter = FakeAdapter()
        adapter.ack_override = _cumulative_ack("b-restart", "40", "150.0")
        engine = _engine(adapter, state_path)
        initialize_fresh(engine)
        engine.start(sync_from_broker=False)
        try:
            assert engine.submit_intent(_make_intent()).accepted
            client_id = next(iter(engine.order_states))
            adapter.tick_status[client_id] = _status(
                "b-restart", status="PartiallyFilled", filled="70", price="152.0",
                price_is_cumulative_avg=True)
            engine.poll_fills()
            assert engine._order_filled_quantity[client_id] == 70
            assert float(engine._order_filled_notional[client_id]) == pytest.approx(
                10640.0, abs=1e-6)
        finally:
            engine.stop()

        adapter2 = FakeAdapter()
        engine2 = _engine(adapter2, state_path)
        engine2.start(sync_from_broker=False)
        try:
            assert engine2._order_filled_quantity[client_id] == 70
            assert float(engine2._order_filled_notional[client_id]) == pytest.approx(
                10640.0, abs=1e-6)
            adapter2.tick_status[client_id] = _status(
                "b-restart", status="Filled", filled="100", price="155.0",
                price_is_cumulative_avg=True)
            engine2.poll_fills()

            pos = engine2.portfolio.get_position("AAPL")
            assert pos is not None and pos.quantity == 100
            assert float(pos.cost_basis.amount) == pytest.approx(155.0, abs=1e-9)
            final = _fill_events(engine2, "OrderFilled")[-1]
            assert final["filled_quantity"] == 30
            assert float(final["fill_price"]) == pytest.approx(162.0, abs=1e-9)
        finally:
            engine2.stop()


def test_legacy_fill_events_rebuild_applied_notional():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = str(Path(tmp) / "state.json")
        db_path = state_path.replace(".json", ".db")
        store = EventStore(db_path)
        store.append(EventEnvelope(
            "OrderSubmitted", "Execution", "legacy-cum", "test_python",
            json.dumps({
                "client_order_id": "legacy-cum",
                "instrument_id": "AAPL",
                "side": "BUY",
                "quantity": "100",
                "price": "0",
            }),
        ))
        for delta, px in ((40, "150.0"), (30, "152.0")):
            store.append(EventEnvelope(
                "OrderFilled", "Execution", "legacy-cum", "test_python",
                json.dumps({
                    "client_order_id": "legacy-cum",
                    "instrument_id": "AAPL",
                    "side": "BUY",
                    "filled_quantity": delta,
                    "fill_price": px,
                }),
            ))
        store.close()

        engine = _engine(FakeAdapter(), state_path)
        engine.start(sync_from_broker=False)
        try:
            assert engine._order_filled_quantity["legacy-cum"] == 70
            # Legacy fill prices were cumulative averages; replay reproduces
            # the notional the portfolio actually booked.
            assert float(engine._order_filled_notional["legacy-cum"]) == pytest.approx(
                10560.0, abs=1e-6)

            with engine._lock:
                fill = engine._absorb_broker_fill(
                    "legacy-cum", OrderStateMachine(), 100, "155",
                    update_sm=False, price_is_cumulative_avg=True)
            assert fill is not None
            assert float(fill.price) == pytest.approx(4940 / 30, abs=1e-9)
            assert float(engine._order_filled_notional["legacy-cum"]) == pytest.approx(
                15500.0, abs=1e-6)
        finally:
            engine.stop()
