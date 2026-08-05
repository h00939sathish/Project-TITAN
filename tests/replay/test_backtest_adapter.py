from titan.execution.backtest_adapter import BacktestAdapter
from titan.execution._broker_types import (
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    AdapterSessionState,
)
from titan._core import ApprovedOrderIntent, Money

SAMPLE_BAR = {
    "instrument_id": "AAPL",
    "timestamp": "2026-01-02T00:00:00",
    "open": 150, "high": 152, "low": 149, "close": 151.50, "volume": 1000000,
}


def _intent(**kw) -> ApprovedOrderIntent:
    fields = dict(
        risk_decision_id="rd-1",
        intent_id="int-1",
        client_order_id="co-1",
        instrument_id="AAPL",
        side="BUY",
        quantity="10",
        order_type="LIMIT",
        time_in_force="DAY",
        risk_profile_version="1.0",
        price="151.50",
    )
    fields.update(kw)
    return ApprovedOrderIntent(**fields)


class TestBacktestAdapter:
    def test_place_order_returns_fill(self):
        adapter = BacktestAdapter([SAMPLE_BAR])
        adapter.advance_to(SAMPLE_BAR)
        ack = adapter.place_order(_intent())
        assert ack.accepted
        assert ack.fill_quantity == "10"

    def test_place_order_without_bar_rejected(self):
        adapter = BacktestAdapter([])
        ack = adapter.place_order(_intent())
        assert not ack.accepted
        assert ack.rejection_reason is not None

    def test_positions_returns_empty(self):
        adapter = BacktestAdapter([])
        snap = adapter.positions("test-1")
        assert snap.positions == []

    def test_holdings_returns_default(self):
        adapter = BacktestAdapter([])
        bal = adapter.holdings("test-1")
        assert bal.cash.amount == "100000"
        assert bal.currency == "USD"
        assert bal.timestamp is not None

    def test_authenticate_returns_session(self):
        adapter = BacktestAdapter([])
        session = adapter.authenticate()
        assert session.state == AdapterSessionState.CONNECTED

    def test_heartbeat_returns_healthy(self):
        adapter = BacktestAdapter([])
        health = adapter.heartbeat()
        assert health.connected

    def test_cancel_returns_ack(self):
        adapter = BacktestAdapter([])
        cancel = adapter.cancel(BrokerOrderId(id="test-1"))
        assert cancel.accepted
