# Paper Session Admission and FX Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the IBKR paper-session path fail closed on unavailable broker truth and accurately report that FX remains simulation-only until its broker-execution ADR is accepted.

**Architecture:** Paper-session admission registers its canonical equity contract before startup, synchronizes against broker snapshots, and stops routing whenever either snapshot cannot be obtained. FX remains a deterministic simulation/backtest capability under accepted ADR-014; an IBKR `CASH`/`IDEALPRO` contract is a proposed future broker-boundary change, not a switch to enable now.

**Tech Stack:** Python 3.14, pytest, IBKR TWS API (`ibapi`), TITAN PyO3 core.

## Global Constraints

- Paper-only: never place a paper or live broker order while implementing or testing this plan.
- Preserve `TradeIntent -> RiskGate -> ApprovedOrderIntent -> BrokerAdapter`; no strategy may call a broker directly.
- Fail closed on broker disconnect, missing snapshot, drift, unknown instrument, or unqualified strategy/timeframe.
- FX order quantities are 1,000-unit micro-lot multiples and USD-quote pairs only under ADR-014.
- Do not enable an IBKR FX route or accept a live TWS port until a dedicated broker-execution ADR, FX specification, monitoring, rollback, and Architecture Council/Risk Owner approval exist.

---

### Task 1: Fail closed at paper-engine reconciliation

**Files:**

- Modify: `src/titan/execution/engine.py`
- Modify: `tests/adapters/test_paper_trading_engine.py`

**Interfaces:**

- Consumes: `BrokerAdapter.positions(account_id)` and `BrokerAdapter.holdings(account_id)`.
- Produces: a triggered kill switch whenever either broker-truth snapshot cannot be fetched.

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_snapshot_failure_triggers_kill_switch(self):
    self.engine.adapter = SnapshotFailureAdapter()
    self.engine.reconcile()
    assert self.engine.risk_gate.kill_switch.blocks_routing()
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q tests/adapters/test_paper_trading_engine.py -k snapshot_failure`

Expected: FAIL because `reconcile()` substitutes an empty/zero snapshot and can return without halting routing.

- [ ] **Step 3: Implement minimal failure handling**

```python
snapshot_fetch_failed = False
try:
    pos_snapshot = self.adapter.positions(self.config.account_id)
except Exception:
    snapshot_fetch_failed = True
try:
    bal_snapshot = self.adapter.holdings(self.config.account_id)
except Exception:
    snapshot_fetch_failed = True
if snapshot_fetch_failed:
    self.risk_gate.trigger_kill_switch()
```

Keep the existing reconciliation result for observability, but never leave routing open after either failure.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q tests/adapters/test_paper_trading_engine.py -k "snapshot_failure or reconcile"`

Expected: PASS.

### Task 2: Admit the TWS paper session only after registered, reconciled broker truth

**Files:**

- Modify: `scripts/ibkr_paper_session.py`
- Test: `tests/adapters/test_paper_session_admission.py`

**Interfaces:**

- Consumes: one canonical `Instrument` for every `INSTRUMENT_CONFIG` key and `PaperTradingEngine.start(sync_from_broker=True)`.
- Produces: no session readiness unless broker snapshots are available and the engine’s risk gate permits routing.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_registered_equity_matches_ingress_instrument_id():
    assert _paper_instruments()["SPY.ARCA"].instrument_id.symbol == "SPY"

def test_engine_starts_with_broker_sync(monkeypatch):
    engine = FakeEngine()
    _start_engine(engine)
    assert engine.start_calls == [True]
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q tests/adapters/test_paper_session_admission.py`

Expected: FAIL because the script registers after startup and calls `engine.start()` without synchronization.

- [ ] **Step 3: Extract the pure helpers and change startup order**

```python
def _paper_instruments() -> dict[str, Instrument]:
    return {"SPY.ARCA": Instrument(...)}

def _start_engine(engine: PaperTradingEngine) -> None:
    for instrument_id, instrument in _paper_instruments().items():
        engine.register_instrument(instrument, instrument_id)
    engine.start(sync_from_broker=True)
```

Call `_start_engine(engine)` before `node.run()`. Abort startup if `engine.risk_gate.kill_switch.blocks_routing()` is true. Do not fetch credentials or submit orders in the test.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q tests/adapters/test_paper_session_admission.py tests/adapters/test_paper_trading_engine.py -m "not paper_order and not live"`

Expected: PASS.

### Task 3: Keep the IBKR adapter paper-only and document the FX execution gate

**Files:**

- Modify: `src/titan/execution/ibkr_adapter.py`
- Modify: `tests/adapters/test_ibkr_adapter.py`
- Modify: `docs/scope/operating-scope.md`
- Create: `specifications/Forex.spec.md`
- Create: `docs/adr/ADR-018-ibkr-paper-forex-execution.md`

**Interfaces:**

- Consumes: an adapter port and the existing accepted ADR-014 FX simulation contract.
- Produces: a paper-only adapter that rejects a live TWS/Gateway port and an unaccepted FX broker-execution proposal.

- [ ] **Step 1: Write the failing paper-port test**

```python
def test_rejects_live_tws_port():
    with pytest.raises(ValueError, match="paper"):
        IBKRPaperAdapter(port=7496)
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest -q tests/adapters/test_ibkr_adapter.py::TestIBKRAdapterConstruction::test_rejects_live_tws_port`

Expected: FAIL because the paper adapter currently accepts port 7496.

- [ ] **Step 3: Implement and draft governance artifacts**

```python
if port not in (TWS_PAPER_PORT, GATEWAY_PAPER_PORT):
    raise ValueError("IBKRPaperAdapter accepts paper TWS/Gateway ports only")
```

`Forex.spec.md` must define USD-quote symbols, micro-lot sizing, canonical IDs, error states, metrics, monitoring, and rollback. ADR-018 must be **Proposed** and state that IBKR FX needs `CASH`/`IDEALPRO`, canonical position mapping, permission/data checks, and acceptance evidence before it can be implemented.

- [ ] **Step 4: Verify green**

Run: `python -m pytest -q tests/adapters/test_ibkr_adapter.py tests/integration/test_forex_simulation.py -m "not paper_order and not live"`

Expected: PASS; no IBKR connection occurs.

### Task 4: Record and verify the non-trading diagnostics

**Files:**

- Modify: `docs/runbooks/paper-session.md`
- Modify: `docs/scope/operating-scope.md`

- [ ] **Step 1: Add readiness checks**

Record: registered instruments; a successful broker snapshot; reconciliation severity; kill-switch/trading state; closed bars per `(instrument, timeframe)`; qualified variants; proposals; risk rejections; broker acknowledgements/fills.

- [ ] **Step 2: Reconcile contradictory FX scope text**

Make `operating-scope.md` list exactly the four USD-quote pairs accepted by ADR-014: EUR/USD, GBP/USD, AUD/USD, and NZD/USD. State explicitly that IBKR FX execution is not approved.

- [ ] **Step 3: Run final evidence**

Run: `cargo test --manifest-path core/Cargo.toml`

Run: `python -m pytest -q tests/risk tests/recovery tests/adapters/test_ibkr_adapter.py tests/adapters/test_paper_trading_engine.py tests/adapters/test_paper_session_admission.py tests/integration/test_forex_simulation.py -m "not paper_order and not live"`

Expected: all selected tests pass; the commands never send an order to TWS/IBKR.

## Self-review

- Specification coverage: Task 1 and 2 preserve Broker/Execution/Risk recovery gates; Task 3 prevents a paper adapter from becoming a live route and prepares the required FX boundary artifacts; Task 4 makes non-trading evidence observable.
- Placeholder scan: no incomplete implementation marker is used.
- Type consistency: the plan uses existing `PaperTradingEngine.start(sync_from_broker: bool)`, `BrokerAdapter` snapshots, `Instrument`, and `RiskGate` interfaces.

