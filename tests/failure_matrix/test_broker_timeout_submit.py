"""Broker timeout during order submit — order stays pending, reconcile resolves."""
import pytest
from titan._core import TradeIntent, PortfolioEngine, Money, ReconciliationEngine, ReconciliationConfig
from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality


class TestBrokerTimeoutSubmit:
    def test_timeout_submit_remains_pending(self):
        adapter = SimulatedAdapter()
        adapter.set_default_fill_quality(SimFillQuality.TIMEOUT)
        intent = TradeIntent("s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", price="150")
        order = adapter.submit_order(
            order_id="ord-timeout-1",
            instrument_id=intent.instrument_id,
            side=intent.side.lower(),
            quantity=int(intent.quantity),
            price="150",
        )
        assert order.status == "pending", f"Expected PENDING, got {order.status}"
        assert len(order.fills) == 0

    def test_reconcile_clean_after_timeout(self):
        adapter = SimulatedAdapter()
        adapter.set_default_fill_quality(SimFillQuality.TIMEOUT)
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        intent = TradeIntent("s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", price="150")
        order = adapter.submit_order("ord-to-2", "AAPL", "buy", 100, "150")
        assert order.status == "pending"
        # Reconcile: broker has no position (timeout means order never reached broker)
        broker_positions = []
        recon = ReconciliationEngine(
            ReconciliationConfig(warning_drift_fraction=0.01, critical_drift_fraction=0.05)
        )
        result = recon.compare(
            portfolio=portfolio,
            broker_positions=broker_positions,
            broker_cash=Money("100000", "USD"),
        )
        assert result.position_drifts == [], f"Expected clean reconciliation, got drifts: {result.position_drifts}"
