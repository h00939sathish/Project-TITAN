# Paper Reconciliation Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make simulated paper reconciliation consume deterministic adapter truth and remain halted when truth cannot be fetched.

**Architecture:** The in-memory adapter remains non-networked, but its position and balance snapshots must derive from filled orders. Boot recovery treats unavailable truth as an unreconciled, halted condition.

**Tech Stack:** Python, pytest, PyO3/Rust core types, Decimal.

## Global Constraints

- Simulation only: no credentials, network, paper order, or live order.
- Preserve TradeIntent -> risk -> ApprovedOrderIntent -> adapter authority.
- Use Decimal for money; do not alter dependencies, configuration, or risk limits.
- Preserve unrelated dirty-worktree changes.

---

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

### Task 3: Prove paper-engine reconciliation against adapter truth

**Files:**

- Modify: tests/adapters/test_paper_trading_engine.py
- Modify: tests/integration/test_paper_vertical_slice.py

**Interfaces:**

- Consumes: PaperTradingEngine.reconcile after simulated fills.
- Produces: proof that matching state is InSync and critical divergence triggers the kill switch.

- [ ] **Step 1: Strengthen the existing full-cycle assertion**

    result = self.engine.reconcile()
    assert result.severity == ReconciliationDriftSeverity.InSync
    assert result.position_drifts == []

Add a test-only adapter subclass returning a deliberately different BrokerPositionSnapshot. Assert critical reconciliation drift and self.engine.risk_gate.kill_switch.blocks_routing().

- [ ] **Step 2: Verify red, then green**

Run: python -m pytest -q tests/adapters/test_paper_trading_engine.py tests/integration/test_paper_vertical_slice.py

Expected before Task 1: exact InSync assertion fails after a fill. Expected after Tasks 1 and 2: PASS.

- [ ] **Step 3: Run focused safety evidence**

Run: python -m pytest -q tests/risk tests/recovery tests/adapters/test_simulated_adapter_contract.py tests/adapters/test_paper_trading_engine.py tests/integration/test_paper_vertical_slice.py -m "not live and not paper_order"

Expected: PASS; no paper or live order is sent.

### Task 4: Record the paper-readiness gate

**Files:**

- Modify: docs/runbooks/paper-session.md
- Modify: specifications/ORR-checklist.md
- Modify: docs/adr/ADR-0006-paper-broker-certification.md

- [ ] **Step 1: Add the runbook rule**

Before enabling a paper strategy, record a successful reconciliation whose position and cash snapshots come from the configured adapter. A missing or failed snapshot is a HALTED condition; do not replace it with portfolio state.

- [ ] **Step 2: Add the ORR criterion**

- [ ] Adapter truth check: an executed simulated fill reconciles InSync; a snapshot fetch failure and critical divergence both leave routing HALTED.

- [ ] **Step 3: Verify documentation and code checks**

Run: rg -n "broker truth snapshot unavailable|Adapter truth check" docs specifications
Run: cargo test --manifest-path core/Cargo.toml
Run: python -m pytest -q tests/risk tests/recovery tests/adapters/test_simulated_adapter_contract.py tests/adapters/test_paper_trading_engine.py tests/integration/test_paper_vertical_slice.py -m "not live and not paper_order"

Expected: every phrase appears and all checks pass.

## Self-review

- Spec coverage: Tasks 1 and 3 implement Broker.spec.md snapshots; Task 2 enforces fail-closed recovery from Risk.spec.md and ADR-0004; Task 4 provides ORR and runbook evidence.
- Placeholder scan: no incomplete marker or unspecified command remains.
- Type consistency: snapshot types remain BrokerPositionSnapshot and BrokerBalanceSnapshot; recovery emits the explicit flag read by transition_on_boot.

## Execution Handoff

Plan complete and saved to docs/superpowers/plans/2026-07-26-paper-reconciliation-readiness.md. Execute one task at a time, review its diff, and rerun stated verification. Do not run paper or live orders as part of this plan.
