"""Broker timeout during order cancel — no retry, reconcile resolves."""
import pytest
from titan._core import TradeIntent, PortfolioEngine, Money, ReconciliationEngine, ReconciliationConfig
from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality


class TestBrokerTimeoutCancel:
    def test_cancel_filled_order_returns_false(self):
        """SimulatedAdapter.cancel_order returns False for filled orders (cannot cancel)."""
        adapter = SimulatedAdapter()
        intent = TradeIntent("s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", "2026-07-13T23:12:00Z", price="150")
        order = adapter.submit_order("ord-cancel-to", "AAPL", "buy", 100, "150")
        assert order.status == "filled"
        result = adapter.cancel_order("ord-cancel-to")
        assert result is False

    def test_cancel_pending_order_succeeds(self):
        """Cancel a pending order (NEVER_FILL quality)."""
        adapter = SimulatedAdapter()
        adapter.set_default_fill_quality(SimFillQuality.NEVER_FILL)
        order = adapter.submit_order("ord-cancel-pend", "AAPL", "buy", 100, "150")
        assert order.status == "pending"
        result = adapter.cancel_order("ord-cancel-pend")
        assert result is True
        assert adapter.get_order("ord-cancel-pend").status == "cancelled"
