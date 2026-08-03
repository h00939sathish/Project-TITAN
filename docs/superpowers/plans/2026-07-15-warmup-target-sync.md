# Warmup Target Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a flat paper portfolio receives the current long target exactly once when historical strategy warmup has already mutated the strategy's private position state.

**Architecture:** `StrategyBridge.warmup()` will retain the latest directional signal returned while loading pre-current-bar history. `on_price()` will replace that value whenever a current bar has a direction, or use the retained BUY when the current bar has no new signal, the bridge is flat, and no duplicate intent has been emitted. A current-bar signal remains authoritative, and a historical SELL never opens a short position because the bridge is explicitly long-only.

**Tech Stack:** Python 3.12+, pytest, TITAN StrategyBridge, existing structured session logs and intent counters.

## Global Constraints

- The change is paper-only and does not change broker, portfolio, risk-gate, or kill-switch authority.
- All emitted intents continue through `PaperTradingEngine.submit_intent()` and its deterministic risk gate.
- The bridge remains long-only: SELL does not establish a flat portfolio position.
- No state-file schema change is permitted; restart deduplication continues to use `last_bar_dates` and `last_intent_sides`.
- Monitoring uses existing structured strategy submission/rejection logs and `intents_evaluated` / `intents_rejected`; rollback is to stop the runner, retain the state and logs, revert this bridge change, and restart only after reconciliation is clean.

---

### Task 1: Specify and ratify strategy-runtime startup behavior

**Files:**
- Create: `specifications/StrategyRuntime.spec.md`
- Modify: `specifications/README.md`
- Create: `docs/adr/ADR-013-strategy-warmup-startup-target.md`

**Interfaces:**
- Consumes: historical daily closes, the current daily close, `StrategyBridge.set_position()`.
- Produces: at most one `TradeIntent` for a flat long-only portfolio at startup, submitted through the existing risk pipeline.

- [x] **Step 1: Write the specification and acceptance evidence**

```markdown
Warmup loads all bars before the current bar and emits no intent. It records the latest historical directional signal. On the first current bar, an explicit current signal wins; otherwise a retained historical BUY may emit one BUY only when the reconciled portfolio is flat. A retained historical SELL emits nothing for a flat long-only portfolio.
```

- [x] **Step 2: Record the decision, rollback, and monitoring in ADR-013**

```markdown
Status: Accepted

Rollback: trigger the kill switch, preserve the session state and logs, revert the bridge-only change, reconcile broker truth, then restart.
Monitoring: review structured strategy accept/reject logs and the existing intent counters for the one-time startup intent.
```

- [x] **Step 3: Verify documentation links**

Run: `rg -n "StrategyRuntime.spec.md|warmup|startup" specifications/README.md specifications/StrategyRuntime.spec.md docs/adr/ADR-013-strategy-warmup-startup-target.md`

Expected: the specification is indexed and the scoped ADR records the accepted startup semantics, rollback, monitoring, and acceptance tests without changing the broader broker-paper ADR.

### Task 2: Lock the startup bug with a regression test

**Files:**
- Modify: `tests/strategies/test_bridge.py`

**Interfaces:**
- Consumes: `StrategyBridge.warmup(instrument, prices)` and `StrategyBridge.on_price(instrument, price, bar_date)`.
- Produces: a BUY intent exactly once when time-series momentum is long after warmup but returns no transition on the current bar.

- [x] **Step 1: Write the failing test**

```python
def test_warmup_long_target_enters_flat_portfolio_once(self):
    bridge = StrategyBridge("time-series-momentum", {"lookback": 2})
    bridge.warmup("SPY", [100.0, 101.0, 102.0])
    bridge.set_position("SPY", False)

    intent = bridge.on_price("SPY", 103.0, bar_date="2026-07-15")

    assert intent is not None
    assert intent.side == "BUY"
    assert bridge.on_price("SPY", 103.0, bar_date="2026-07-15") is None
```

- [x] **Step 2: Run the regression test and verify it is red**

Run: `python -m pytest tests/strategies/test_bridge.py::TestStrategyBridgeWarmup::test_warmup_long_target_enters_flat_portfolio_once -q`

Expected: FAIL because `intent is None` before the bridge records the warmup target.

- [x] **Step 3: Write and run the stale-direction regression test**

```python
def test_current_signal_replaces_warmup_target(self):
    bridge = StrategyBridge("time-series-momentum", {"lookback": 2})
    bridge.warmup("SPY", [100.0, 101.0, 102.0])
    bridge.set_position("SPY", True)

    assert bridge.on_price("SPY", 90.0, bar_date="2026-07-15").side == "SELL"
    assert bridge.on_price("SPY", 89.0, bar_date="2026-07-16") is None
```

Run: `python -m pytest tests/strategies/test_bridge.py::TestStrategyBridgeWarmup::test_current_signal_replaces_warmup_target -q`

Expected before implementation: FAIL because the stale retained BUY emits an intent after SELL.

### Task 3: Implement the minimal bridge synchronization

**Files:**
- Modify: `src/titan/strategies/bridge.py`
- Test: `tests/strategies/test_bridge.py`

**Interfaces:**
- Consumes: directional signal return values from registered strategy functions.
- Produces: `StrategyBridge._warmup_signals: dict[str, str]` and existing `TradeIntent | None` behavior.

- [x] **Step 1: Retain the latest warmup direction**

```python
self._warmup_signals: dict[str, str] = {}

for price in prices:
    signal = fn({"close": price})
    if signal in {"BUY", "SELL"}:
        self._warmup_signals[instrument] = signal
```

- [x] **Step 2: Use the retained BUY only when the current bar has no signal**

```python
signal = fn({"close": price})
if signal in {"BUY", "SELL"}:
    self._warmup_signals[instrument] = signal
if signal is None:
    signal = self._warmup_signals.get(instrument)
if signal is None:
    return None
```

The existing position and duplicate-side guards remain unchanged, so a retained SELL is rejected when flat and a retained BUY cannot repeat after the bridge records the position.

- [x] **Step 3: Run the targeted test and verify it is green**

Run: `python -m pytest tests/strategies/test_bridge.py::TestStrategyBridgeWarmup::test_warmup_long_target_enters_flat_portfolio_once -q`

Expected: `1 passed`.

### Task 4: Verify runner-adjacent safety behavior

**Files:**
- Test: `tests/strategies/test_bridge.py`
- Test: `tests/strategies/test_momentum.py`

**Interfaces:**
- Consumes: long-only SELL guard, bar-date duplicate guard, time-series momentum transitions.
- Produces: regression evidence that no duplicate or unauthorized short intent is introduced.

- [x] **Step 1: Run the focused strategy suites**

Run: `python -m pytest tests/strategies/test_bridge.py tests/strategies/test_momentum.py -q`

Expected: all tests pass.

- [x] **Step 2: Run static analysis for the changed Python files**

Run: `python -m ruff check src/titan/strategies/bridge.py tests/strategies/test_bridge.py`

Expected: `All checks passed!`.

- [x] **Step 3: Review the final diff and preserve unrelated work**

Run: `git diff -- src/titan/strategies/bridge.py tests/strategies/test_bridge.py specifications/StrategyRuntime.spec.md specifications/README.md docs/adr/ADR-013-strategy-warmup-startup-target.md`

Expected: only the startup target contract, ADR decision, bridge behavior, and regression test are changed.
