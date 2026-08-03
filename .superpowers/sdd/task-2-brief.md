### Task 2: Fail closed when boot reconciliation cannot fetch truth

**Files:**

- Modify: src/titan/recovery/restart.py
- Modify: tests/recovery/test_restart.py

**Interfaces:**

- Consumes: adapter positions and holdings snapshots.
- Produces: snapshot_fetch_failed=True, reconciled=False, and HALTED (broker truth unavailable) when either fetch fails.

- [ ] **Step 1: Write the failing recovery test**

    class SnapshotFailureAdapter:
        def positions(self, account_id: str):
            raise RuntimeError("positions unavailable")
        def holdings(self, account_id: str):
            raise RuntimeError("holdings unavailable")

    def test_boot_stays_halted_when_broker_truth_is_unavailable():
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        recon = ReconciliationEngine(ReconciliationConfig(0.05, 0.01))
        result = reconcile_on_boot(portfolio, SnapshotFailureAdapter(), recon)
        gate = RiskGate(RiskConfig.default())
        assert result["snapshot_fetch_failed"] is True
        assert result["reconciled"] is False
        assert transition_on_boot(result, gate) == "HALTED (broker truth unavailable)"
        assert gate.trading_state == TradingState.Halted

- [ ] **Step 2: Verify red**

Run: python -m pytest -q tests/recovery/test_restart.py::TestRecoverFromEventStore::test_boot_stays_halted_when_broker_truth_is_unavailable

Expected: FAIL because current recovery swallows snapshot exceptions.

- [ ] **Step 3: Implement explicit failure state**

Set snapshot_fetch_failed in each snapshot exception handler. When it is true, return:
    {
        "has_drift": True,
        "drift_count": 0,
        "drift_details": ["broker truth snapshot unavailable"],
        "reconciled": False,
        "snapshot_fetch_failed": True,
    }

At the start of transition_on_boot, detect this flag, set TradingState.Halted, and return HALTED (broker truth unavailable).

- [ ] **Step 4: Verify green**

Run: python -m pytest -q tests/recovery/test_restart.py tests/adapters/test_simulated_adapter_contract.py

Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/titan/recovery/restart.py tests/recovery/test_restart.py
    git commit -m "fix: halt recovery when broker truth is unavailable"


