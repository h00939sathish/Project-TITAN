"""Contract tests for the SimulatedAdapter — proves it meets Broker.spec.md requirements."""

from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality


class TestSimulatedAdapterContract:
    """Proves the adapter meets the broker adapter contract per Broker.spec.md."""

    def setup_method(self):
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)

    def test_submit_and_fill(self):
        order = self.adapter.submit_order("ord-1", "AAPL", "buy", 100, "150.00")
        assert order.status == "filled"
        assert order.filled_quantity == 100

    def test_submit_and_reject(self):
        self.adapter.set_default_fill_quality(SimFillQuality.REJECT)
        order = self.adapter.submit_order("ord-2", "AAPL", "buy", 100, "150.00")
        assert order.status == "rejected"

    def test_partial_fill_then_full(self):
        self.adapter.set_default_fill_quality(SimFillQuality.PARTIAL_THEN_FULL)
        order = self.adapter.submit_order("ord-3", "AAPL", "buy", 100, "150.00")
        assert order.status == "partially_filled"
        assert order.filled_quantity == 50
        updated = self.adapter.tick("ord-3")
        assert updated is not None
        assert updated.status == "filled"
        assert updated.filled_quantity == 100

    def test_timeout_simulated(self):
        self.adapter.set_default_fill_quality(SimFillQuality.TIMEOUT)
        order = self.adapter.submit_order("ord-4", "AAPL", "buy", 100, "150.00")
        assert order.status == "pending"

    def test_never_fill(self):
        self.adapter.set_default_fill_quality(SimFillQuality.NEVER_FILL)
        order = self.adapter.submit_order("ord-5", "AAPL", "buy", 100, "150.00")
        assert order.status == "pending"
        updated = self.adapter.tick("ord-5")
        assert updated is None

    def test_cancel_pending(self):
        self.adapter.set_default_fill_quality(SimFillQuality.NEVER_FILL)
        order2 = self.adapter.submit_order("ord-7", "AAPL", "buy", 100, "150.00")
        assert self.adapter.cancel_order("ord-7")

    def test_cancel_filled_order_fails(self):
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.adapter.submit_order("ord-8", "AAPL", "buy", 100, "150.00")
        assert not self.adapter.cancel_order("ord-8")

    def test_open_orders(self):
        self.adapter.set_default_fill_quality(SimFillQuality.NEVER_FILL)
        self.adapter.submit_order("ord-9", "AAPL", "buy", 100, "150.00")
        self.adapter.submit_order("ord-10", "MSFT", "sell", 50, "400.00")
        assert len(self.adapter.open_orders) == 2

    def test_filled_orders(self):
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.adapter.submit_order("ord-11", "AAPL", "buy", 100, "150.00")
        self.adapter.submit_order("ord-12", "MSFT", "sell", 50, "400.00")
        assert len(self.adapter.filled_orders) == 2

    def test_get_order_nonexistent(self):
        assert self.adapter.get_order("nonexistent") is None

    def test_multiple_independent_orders(self):
        self.adapter.set_default_fill_quality(SimFillQuality.PARTIAL_THEN_FULL)
        o1 = self.adapter.submit_order("m1", "AAPL", "buy", 100, "150")
        o2 = self.adapter.submit_order("m2", "MSFT", "sell", 50, "400")
        assert o1.instrument_id == "AAPL"
        assert o2.instrument_id == "MSFT"
        assert o1.status == "partially_filled"
        assert o2.status == "partially_filled"
        self.adapter.tick("m1")
        self.adapter.tick("m2")
        assert self.adapter.get_order("m1").status == "filled"
        assert self.adapter.get_order("m2").status == "filled"
