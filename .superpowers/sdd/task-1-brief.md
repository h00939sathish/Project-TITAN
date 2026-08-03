### Task 1: Derive simulated broker truth from filled orders

**Files:**

- Modify: src/titan/execution/simulated_adapter.py
- Test: tests/adapters/test_simulated_adapter_contract.py

**Interfaces:**

- Consumes: SimOrderState filled quantities.
- Produces: position and balance snapshots representing adapter fills.

- [ ] **Step 1: Write the failing snapshot contract test**

    def test_snapshots_reflect_filled_buy_and_sell(self):
        self.adapter.submit_order("buy-1", "AAPL", "buy", 100, "150.00")
        self.adapter.submit_order("sell-1", "AAPL", "sell", 40, "155.00")
        positions = self.adapter.positions("paper-1").positions
        balance = self.adapter.holdings("paper-1")
        assert len(positions) == 1
        assert positions[0].instrument_id == "AAPL"
        assert str(positions[0].side).upper() == "LONG"
        assert positions[0].quantity == 60
        assert balance.cash.amount == "91200.00"

- [ ] **Step 2: Verify red**

Run: python -m pytest -q tests/adapters/test_simulated_adapter_contract.py::TestSimulatedAdapterContract::test_snapshots_reflect_filled_buy_and_sell

Expected: FAIL because positions is empty and holdings is fixed at 100000.

- [ ] **Step 3: Implement deterministic aggregation**

Add Decimal import. Add a helper that iterates self._orders, adds filled_quantity for buy and subtracts it for sell, keyed by instrument. Make positions emit non-zero BrokerPosition records with LONG or SHORT and absolute quantity. Make holdings begin with Decimal("100000"), subtract each filled buy price-times-quantity and add each filled sell price-times-quantity. Construct cash, portfolio_value, buying_power, and equity with Money(str(cash), "USD"). Preserve rejects, timeouts, pending, partial-fill, and cancellation behavior.

- [ ] **Step 4: Verify green**

Run: python -m pytest -q tests/adapters/test_simulated_adapter_contract.py

Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/titan/execution/simulated_adapter.py tests/adapters/test_simulated_adapter_contract.py
    git commit -m "fix: derive simulated broker reconciliation snapshots"


