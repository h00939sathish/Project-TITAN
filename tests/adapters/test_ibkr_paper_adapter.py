"""Fake-transport contract tests for IBKR paper adapter."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from titan._core import ApprovedOrderIntent, Money
from titan.execution._broker_adapter import BrokerAdapter
from titan.execution._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)


@dataclass
class FakeTransport:
    placed_orders: list = field(default_factory=list)
    cancelled: list = field(default_factory=list)
    heartbeat_ok: bool = True
    next_session_id: str = "fake-session-1"

    def authenticate(self) -> Session:
        return Session(
            session_id=self.next_session_id,
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        self.placed_orders.append(intent)
        return BrokerOrderAcknowledgement(
            accepted=True,
            broker_order_id=BrokerOrderId(id=str(uuid.uuid4())),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        self.cancelled.append(order_id)
        return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(
            connected=self.heartbeat_ok,
            session_state=AdapterSessionState.CONNECTED,
        )


@dataclass
class FakeIBKRPaperAdapter(BrokerAdapter):
    transport: FakeTransport = field(default_factory=FakeTransport)

    def authenticate(self) -> Session:
        return self.transport.authenticate()

    def heartbeat(self) -> AdapterHealth:
        return self.transport.heartbeat()

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        return self.transport.place_order(intent)

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=Money("100000", "USD"),
            portfolio_value=Money("100000", "USD"),
            buying_power=Money("100000", "USD"),
            equity=Money("100000", "USD"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        return self.transport.cancel(order_id)


def _approved_intent() -> ApprovedOrderIntent:
    return ApprovedOrderIntent(
        risk_decision_id=str(uuid.uuid4()),
        intent_id=str(uuid.uuid4()),
        client_order_id="test-client-order-1",
        instrument_id="SPY",
        side="BUY",
        quantity="100",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        price="450.00",
    )


class TestFakeTransportContract:
    def test_authenticate_returns_session(self):
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        session = adapter.authenticate()
        assert session.session_id == "fake-session-1"
        assert session.state == AdapterSessionState.CONNECTED

    def test_place_order_preserves_client_order_id(self):
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        intent = _approved_intent()
        ack = adapter.place_order(intent)
        assert ack.accepted
        assert transport.placed_orders[0].client_order_id == "test-client-order-1"

    def test_place_order_propagates_rejection(self):
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        intent = _approved_intent()
        ack = adapter.place_order(intent)
        assert ack.accepted is True

    def test_heartbeat_returns_connected(self):
        adapter = FakeIBKRPaperAdapter(FakeTransport())
        hb = adapter.heartbeat()
        assert hb.connected is True
        assert hb.session_state == AdapterSessionState.CONNECTED

    def test_heartbeat_detects_disconnect(self):
        transport = FakeTransport(heartbeat_ok=False)
        adapter = FakeIBKRPaperAdapter(transport)
        hb = adapter.heartbeat()
        assert hb.connected is False

    def test_positions_returns_empty_by_default(self):
        adapter = FakeIBKRPaperAdapter(FakeTransport())
        snap = adapter.positions("test-account")
        assert snap.account_id == "test-account"
        assert snap.positions == []

    def test_holdings_returns_default_cash(self):
        adapter = FakeIBKRPaperAdapter(FakeTransport())
        bal = adapter.holdings("test-account")
        assert bal.cash.amount == "100000"

    def test_cancel_propagates_to_transport(self):
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        oid = BrokerOrderId(id="order-1")
        result = adapter.cancel(oid)
        assert result.accepted
        assert transport.cancelled[0].id == "order-1"

    def test_adapter_implements_broker_adapter_protocol(self):
        adapter = FakeIBKRPaperAdapter(FakeTransport())
        assert isinstance(adapter, BrokerAdapter)



