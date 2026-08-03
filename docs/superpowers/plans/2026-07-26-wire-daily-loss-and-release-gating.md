# Wire Daily Loss Enforcement and Fix Kill-Switch Release Gating

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Fix the daily loss risk control that is currently decorative (always passes) and fix the kill-switch release sequencing so it properly gates on reconciliation and resets trading state.

**Architecture:** Rust RiskConfig/PortfolioEngine keep daily loss values as negative Decimals; the evaluate() comparison operator must account for sign. Python PaperTradingEngine.release_kill_switch() must reset trading_state to Active and properly sequence the release through Releasing state. CLI's release command must use the actual engine state, not a fresh empty portfolio.

**Tech Stack:** Python, pytest, PyO3/Rust core types, Decimal.

## Global Constraints

- Simulation only: no credentials, network, paper order, or live order.
- Preserve TradeIntent -> risk -> ApprovedOrderIntent -> adapter authority.
- Use Decimal for money; do not alter dependencies, configuration, or risk limits.
- Preserve unrelated dirty-worktree changes.

## Evidence

- `core/src/risk.rs:407-415`: `dl.amount > max_daily_loss.amount` with negative loss → always false for positive max_daily_loss.
- `tests/adapters/test_broker_paper_certification.py:304-312`: Explicit workaround with `max_daily_loss="-100000"` and `ponytail:` comment acknowledging the bug.
- `src/titan/execution/engine.py:934-946`: `release_kill_switch()` calls `release_initiated()` then immediately `release_completed()` without resetting `trading_state`.
- `src/titan/cli.py:72-76`: CLI release creates fresh empty portfolio + simulated adapter for reconciliation — meaningless check.

---

### Task 1: Fix daily loss comparison operator

**Files:**
- Modify: `core/src/risk.rs`
- Modify: `tests/adapters/test_broker_paper_certification.py`

**Interfaces:**
- Consumes: `PortfolioEngine.daily_realized_loss` (negative Decimal).
- Produces: correct rejection when `abs(daily_loss) > max_daily_loss.amount`.

- [ ] **Step 1: Write the failing test**

  Add a new test in `test_broker_paper_certification.py`:
  ```python
  def test_daily_loss_limit_is_enforced(self, gate, portfolio, adapter):
      """A loss exceeding max_daily_loss triggers DailyLossExceeded rejection."""
      portfolio.apply_fill("AAPL", "buy", 100, Money("15000", "USD"))
      portfolio.apply_fill("AAPL", "sell", 100, Money("5000", "USD"))
      # daily_realized_loss = -10000 after 10000 loss, max_daily_loss = 5000
      max_daily_loss = 5000
      config = RiskConfig(max_daily_loss=Money(str(max_daily_loss), "USD"),
                          instrument_eligibility=["AAPL"])
      gate = RiskGate(config)
      snapshot = portfolio.get_snapshot()
      intent = make_intent(instrument="AAPL", quantity="10", price="100")
      verdict = gate.evaluate(intent, current_daily_loss=snapshot.daily_realized_loss)
      assert not verdict.accepted
      assert verdict.reason == RiskReasonCode.DailyLossExceeded
  ```

- [ ] **Step 2: Verify red**

  Run: `python -m pytest -q tests/adapters/test_broker_paper_certification.py::TestPaperCertification::test_daily_loss_limit_is_enforced`

  Expected: FAIL (the loss of -10000 with max 5000: `-10000 > 5000` = false, so it passes when it should reject).

- [ ] **Step 3: Fix the comparison operator**

  In `core/src/risk.rs:407-415`, change:
  ```rust
  if let Some(dl) = current_daily_loss
      && dl.amount > self.config.max_daily_loss.amount
  ```
  to:
  ```rust
  if let Some(dl) = current_daily_loss
      && dl.amount.abs() > self.config.max_daily_loss.amount
  ```

- [ ] **Step 4: Fix the certification test workaround**

  In `tests/adapters/test_broker_paper_certification.py`, find the existing daily loss test that uses `max_daily_loss="-100000"` and restore it to a positive value. Remove the `ponytail:` comment.

- [ ] **Step 5: Verify green**

  Run Rust tests: `cargo test --manifest-path core/Cargo.toml`
  Run: `python -m pytest -q tests/risk tests/adapters/test_broker_paper_certification.py::TestPaperCertification::test_daily_loss_limit_is_enforced`

  Expected: ALL PASS.

- [ ] **Step 6: Commit**

  ```
  git add core/src/risk.rs tests/adapters/test_broker_paper_certification.py
  git commit -m "fix: daily loss comparison operator inverted — losses never caught"
  ```

### Task 2: Fix kill-switch release sequencing

**Files:**
- Modify: `src/titan/execution/engine.py`
- Modify: `src/titan/cli.py`

**Interfaces:**
- Consumes: `KillSwitchState` (Armed → Triggered → Releasing → Released), `TradingState` (Active/Halted).
- Produces: release completes only after clean reconciliation and resets trading_state to Active.

- [ ] **Step 1: Write the failing test**

  In `tests/adapters/test_paper_trading_engine.py`, add to `TestPaperTradingEngineFullPipeline`:
  ```python
  def test_release_kill_switch_resumes_routing(self):
      """After clean reconciliation, release_kill_switch sets Active and allows routing."""
      config = _default_config()
      adapter = SimulatedAdapter()
      adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
      engine = PaperTradingEngine(config, adapter)
      engine.start()
      engine.register_instrument(
          Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
      )
      # Trigger kill switch
      engine.risk_gate.trigger_kill_switch()
      assert engine.risk_gate.kill_switch.blocks_routing()

      # Fill an order so there's something to reconcile
      engine.submit_intent(_make_intent(instrument="AAPL", quantity="10", price="100"))

      # Release
      engine.release_kill_switch()

      # After release: kill switch should not block, trading state should be Active
      assert not engine.risk_gate.kill_switch.blocks_routing()
      assert engine.risk_gate.trading_state == TradingState.Active

      # Routing should work
      intent = _make_intent(instrument="AAPL", quantity="5", price="110")
      result = engine.submit_intent(intent)
      assert result.accepted
  ```

- [ ] **Step 2: Verify red**

  Run: `python -m pytest -q tests/adapters/test_paper_trading_engine.py::TestPaperTradingEngineFullPipeline::test_release_kill_switch_resumes_routing`

  Expected: FAIL because release_kill_switch() doesn't reset trading_state.

- [ ] **Step 3: Fix release_kill_switch()**

  In `src/titan/execution/engine.py:934-946`, change to:
  ```python
  def release_kill_switch(self) -> None:
      result = self.reconcile()
      if result.severity is not None and result.severity == ReconciliationDriftSeverity.Critical:
          raise RuntimeError("Refusing to release kill switch: critical reconciliation drift detected")
      self.risk_gate.release_initiated()
      # Persist the Releasing state so recovery sees it
      self.risk_gate.persist_state(self._event_store)
      self.risk_gate.release_completed()
      self.risk_gate.set_trading_state(TradingState.Active)
      self._save_state()
  ```

- [ ] **Step 4: Fix CLI release command**

  In `src/titan/cli.py`, the release command should either:
  a) Use the actual engine's release_kill_switch() method (if engine is running)
  b) Or at minimum reset trading_state after releasing

  For the CLI, the simplest fix is to add `gate.set_trading_state(TradingState.Active)` after completing the release.

- [ ] **Step 5: Verify green**

  Run: `python -m pytest -q tests/adapters/test_paper_trading_engine.py::TestPaperTradingEngineFullPipeline::test_release_kill_switch_resumes_routing`
  Run: `python -m pytest -q tests/risk tests/adapters/test_paper_trading_engine.py`

  Expected: ALL PASS.

- [ ] **Step 6: Commit**

  ```
  git add src/titan/execution/engine.py src/titan/cli.py
  git commit -m "fix: kill-switch release must reset trading_state to Active"
  ```

### Task 3: End-to-end verification

- [ ] **Step 1: Run full safety suite**

  ```bash
  python -m pytest -q tests/risk tests/recovery tests/adapters/test_simulated_adapter_contract.py tests/adapters/test_paper_trading_engine.py tests/integration/test_paper_vertical_slice.py tests/adapters/test_broker_paper_certification.py -m "not live and not paper_order"
  ```

  Expected: ALL PASS.

- [ ] **Step 2: Run Rust tests**

  ```bash
  cargo test --manifest-path core/Cargo.toml
  ```

  Expected: 77 passed.

## Self-review

- Spec coverage: Task 1 fixes Risk.spec.md daily loss enforcement; Task 2 fixes the release gate from Risk.spec.md and ADR-0004.
- Type consistency: daily_loss remains `Decimal` (negative), max_daily_loss remains `Money` (positive). The only change is comparing absolute values.
- No new configuration, dependencies, or risk limits introduced.

## Execution Handoff

Plan complete and saved. Execute one task at a time, review its diff, and rerun stated verification. Do not run paper or live orders as part of this plan.
