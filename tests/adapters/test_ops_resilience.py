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
from pathlib import Path

import pytest
from fixtures.session_init import initialize_fresh

from titan._core import (
    BrokerPosition,
    ContractType,
    EventStore,
    Instrument,
    InstrumentId,
    KillSwitchState,
    Money,
    OrderState,
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


def _status(order_id, status="Filled", filled="100", price="150.0", instrument="AAPL", side="BUY"):
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
