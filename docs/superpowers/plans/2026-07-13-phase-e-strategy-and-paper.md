# Phase E — Strategy and Paper Operation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal versioned strategy package (moving average crossover) that emits TradeIntents through the existing risk → execution → portfolio pipeline, and certify the SimulatedAdapter as the paper adapter through contract tests.

**Architecture:** Pure Python strategy layer. A `StrategyManifest` defines package identity, data requirements, parameter schema, and universe. A `StrategyRuntime` loads packages and runs signal logic. The SimulatedAdapter (from Phase C) is wrapped with an adapter interface matching the Broker.spec.md trait. Contract tests prove every adapter scenario.

**Tech Stack:** Python 3.14, dataclasses, hashlib, pytest.

## Global Constraints

- Strategy never imports broker, portfolio, risk, or execution code directly — only emits TradeIntents.
- Strategy provenance (package digest) is present on every intent.
- Stale data, unknown instruments, invalid digests, and unsupported params are rejected before intent emission.
- The SimulatedAdapter is the paper adapter — no real broker credentials.
- Adapter contract tests exercise every scenario from FAILURE_MATRIX.md (timeout, reject, partial fill, cancel, reconnect).

---

### Task E1: Minimal versioned strategy package

**Files:**
- Create: `src/titan/strategies/__init__.py`
- Create: `src/titan/strategies/manifest.py`
- Create: `src/titan/strategies/runtime.py`
- Create: `src/titan/strategies/moving_average.py`
- Create: `tests/strategies/__init__.py`
- Create: `tests/strategies/test_moving_average_package.py`

**What to build:**

1. **`src/titan/strategies/manifest.py`** — Strategy manifest definition:

```python
"""Versioned strategy package manifest."""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class StrategyManifest:
    """Immutable manifest for a strategy package."""
    package_id: str
    package_version: str
    package_digest: str = ""
    data_requirements: list[str] = field(default_factory=list)
    parameter_schema: dict[str, Any] = field(default_factory=dict)
    universe: list[str] = field(default_factory=list)
    risk_profile_version: str = "1.0"
    expiry: str = ""
    fixture_refs: list[str] = field(default_factory=list)

    def compute_digest(self) -> str:
        """Compute package digest from identity and requirements."""
        h = sha256()
        h.update(self.package_id.encode())
        h.update(self.package_version.encode())
        for req in sorted(self.data_requirements):
            h.update(req.encode())
        for sym in sorted(self.universe):
            h.update(sym.encode())
        h.update(self.risk_profile_version.encode())
        return h.hexdigest()

    def verify(self) -> bool:
        """Verify the stored digest matches computed digest."""
        if not self.package_digest:
            return False
        return self.package_digest == self.compute_digest()
```

2. **`src/titan/strategies/runtime.py`** — Strategy runtime:

```python
"""Strategy runtime — loads packages and manages lifecycle."""

from hashlib import sha256
from titan._core import TradeIntent


class StrategyRejection(Exception):
    """Raised when a strategy's intent is rejected before emission."""
    pass


class StrategyRuntime:
    """Manages strategy lifecycle and intent emission."""

    def __init__(self):
        self._strategies: dict[str, object] = {}
        self._manifests: dict[str, StrategyManifest] = {}
        self._current_time: str | None = None

    def register(self, strategy_id: str, strategy: object, manifest: StrategyManifest) -> None:
        """Register a strategy with its manifest."""
        if not manifest.verify():
            raise ValueError(f"Manifest digest mismatch for {strategy_id}")
        if strategy_id in self._strategies:
            raise ValueError(f"Strategy {strategy_id} already registered")
        self._strategies[strategy_id] = strategy
        self._manifests[strategy_id] = manifest

    def set_current_time(self, timestamp: str) -> None:
        self._current_time = timestamp

    def emit_intent(self, strategy_id: str, instrument_id: str, side: str,
                    quantity: str, order_type: str = "LIMIT",
                    time_in_force: str = "DAY", price: str | None = None,
                    stop_price: str | None = None) -> TradeIntent:
        """Emit a TradeIntent with strategy provenance attached."""
        manifest = self._manifests.get(strategy_id)
        if not manifest:
            raise StrategyRejection(f"Unknown strategy: {strategy_id}")

        if not manifest.verify():
            raise StrategyRejection(f"Manifest digest mismatch for {strategy_id}")

        if instrument_id not in manifest.universe and manifest.universe:
            raise StrategyRejection(f"Instrument {instrument_id} not in strategy universe")

        return TradeIntent(
            strategy_id=strategy_id,
            strategy_package_digest=manifest.package_digest,
            account_id="paper-1",
            instrument_id=instrument_id,
            side=side,
            quantity=str(quantity),
            order_type=order_type,
            time_in_force=time_in_force,
            risk_profile_version=manifest.risk_profile_version,
            price=price,
            stop_price=stop_price,
        )
```

3. **`src/titan/strategies/moving_average.py`** — Moving average crossover strategy:

```python
"""A deterministic moving-average crossover strategy.

Generates BUY/SELL signals when fast MA crosses above/below slow MA.
Pure calculation — no I/O, no broker/portfolio imports.
"""

from dataclasses import dataclass, field


@dataclass
class MovingAverageCrossover:
    """Simple moving average crossover strategy."""
    
    fast_period: int = 5
    slow_period: int = 20
    
    prices: list[float] = field(default_factory=list)
    
    def update(self, close_price: float) -> str | None:
        """Update with a new close price. Returns signal or None."""
        self.prices.append(close_price)
        if len(self.prices) < self.slow_period + 1:
            return None
        
        fast_ma = sum(self.prices[-self.fast_period:]) / self.fast_period
        slow_ma = sum(self.prices[-self.slow_period:]) / self.slow_period
        
        # Check for crossover
        if len(self.prices) >= self.slow_period + 2:
            prev_fast = sum(self.prices[-(self.fast_period + 1):-1]) / self.fast_period
            prev_slow = sum(self.prices[-(self.slow_period + 1):-1]) / self.slow_period
            
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                return "BUY"
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                return "SELL"
        
        return None
    
    @property
    def is_ready(self) -> bool:
        return len(self.prices) >= self.slow_period
```

4. **`tests/strategies/test_moving_average_package.py`** — Tests:

```python
"""Tests for strategy manifest, runtime, and moving average strategy."""

import pytest
from titan.strategies.manifest import StrategyManifest
from titan.strategies.runtime import StrategyRuntime, StrategyRejection
from titan.strategies.moving_average import MovingAverageCrossover


class TestStrategyManifest:
    def test_manifest_creates_digest(self):
        m = StrategyManifest(
            package_id="ma-cross-v1",
            package_version="1.0.0",
            data_requirements=["ohlcv"],
            parameter_schema={"fast_period": 5, "slow_period": 20},
            universe=["AAPL", "MSFT"],
        )
        digest = m.compute_digest()
        assert len(digest) == 64
        m2 = StrategyManifest(
            package_id="ma-cross-v1",
            package_version="1.0.0",
            data_requirements=["ohlcv"],
            parameter_schema={"fast_period": 5, "slow_period": 20},
            universe=["AAPL", "MSFT"],
        )
        assert m.compute_digest() == m2.compute_digest()

    def test_manifest_verify(self):
        m = StrategyManifest(
            package_id="test", package_version="1",
            package_digest="", universe=["AAPL"],
        )
        assert not m.verify()
        d = m.compute_digest()
        m2 = StrategyManifest(
            package_id="test", package_version="1",
            package_digest=d, universe=["AAPL"],
        )
        assert m2.verify()

    def test_different_params_different_digest(self):
        m1 = StrategyManifest("id", "1", universe=["AAPL"])
        m2 = StrategyManifest("id", "1", universe=["MSFT"])
        assert m1.compute_digest() != m2.compute_digest()


class TestMovingAverageCrossover:
    def test_not_ready_with_few_prices(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=5)
        for p in [100, 101, 102]:
            strat.update(p)
        assert not strat.is_ready

    def test_ready_with_enough_prices(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        for p in [100, 101, 102, 103]:
            strat.update(p)
        assert strat.is_ready

    def test_buy_signal_on_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        # Prices rising — fast should cross above slow
        prices = [100, 101, 102, 103, 104, 105]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "BUY" in signals

    def test_sell_signal_on_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        # Prices falling — fast should cross below slow
        prices = [105, 104, 103, 102, 101, 100]
        signals = []
        for p in prices:
            sig = strat.update(p)
            if sig:
                signals.append(sig)
        assert "SELL" in signals

    def test_no_signal_without_crossover(self):
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        for p in [100, 101, 100, 101, 100, 101]:
            sig = strat.update(p)
            assert sig is None


class TestStrategyRuntime:
    def test_register_and_emit(self):
        manifest = StrategyManifest(
            "ma-cross", "1.0",
            package_digest=StrategyManifest("ma-cross", "1.0", universe=["AAPL"]).compute_digest(),
            universe=["AAPL", "MSFT"],
        )
        rt = StrategyRuntime()
        strat = MovingAverageCrossover()
        rt.register("ma-cross", strat, manifest)
        intent = rt.emit_intent("ma-cross", "AAPL", "BUY", "100", price="150")
        assert intent.strategy_id == "ma-cross"
        assert intent.instrument_id == "AAPL"
        assert intent.strategy_package_digest == manifest.package_digest

    def test_reject_unknown_instrument(self):
        manifest = StrategyManifest(
            "ma-cross", "1.0",
            package_digest=StrategyManifest("ma-cross", "1.0", universe=["AAPL"]).compute_digest(),
            universe=["AAPL"],
        )
        rt = StrategyRuntime()
        rt.register("ma-cross", object(), manifest)
        with pytest.raises(StrategyRejection, match="not in strategy universe"):
            rt.emit_intent("ma-cross", "GOOGL", "BUY", "100")

    def test_reject_unknown_strategy(self):
        rt = StrategyRuntime()
        with pytest.raises(StrategyRejection, match="Unknown strategy"):
            rt.emit_intent("unknown", "AAPL", "BUY", "100")

    def test_reject_bad_digest(self):
        manifest = StrategyManifest("x", "1", package_digest="bad"*16, universe=["AAPL"])
        rt = StrategyRuntime()
        with pytest.raises(ValueError, match="digest mismatch"):
            rt.register("x", object(), manifest)
```

5. **Add to replay test** — also add a test in the replay suite that uses the strategy to emit intents:
(Append to `tests/replay/test_deterministic_replay.py`)
```python
class TestStrategyDrivenReplay:
    def test_ma_strategy_drives_replay(self):
        from titan.strategies.moving_average import MovingAverageCrossover
        from titan.strategies.manifest import StrategyManifest
        from titan.strategies.runtime import StrategyRuntime
        from titan._core import PortfolioEngine, Money, RiskGate, RiskConfig
        
        # Setup
        strat = MovingAverageCrossover(fast_period=2, slow_period=3)
        manifest = StrategyManifest(
            "ma-test", "1.0",
            package_digest=StrategyManifest("ma-test", "1.0", universe=["AAPL"]).compute_digest(),
            universe=["AAPL"],
        )
        rt = StrategyRuntime()
        rt.register("ma-test", strat, manifest)
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        config = RiskConfig([], Money("1000000", "USD"), 1000, 5000,
                            Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000)
        gate = RiskGate(config)
        
        bars = [
            {"close": 100}, {"close": 102}, {"close": 101},
            {"close": 105}, {"close": 108}, {"close": 110},
        ]
        trades = 0
        for bar in bars:
            signal = strat.update(bar["close"])
            if signal:
                intent = rt.emit_intent("ma-test", "AAPL", signal, "10", price=str(int(bar["close"])))
                verdict = gate.evaluate(intent, None, None, None, None)
                if verdict.accepted:
                    portfolio.apply_fill("AAPL", signal.lower(), 10,
                                         Money(str(int(bar["close"])), "USD"))
                    trades += 1
        
        assert trades > 0
        pos = portfolio.get_position("AAPL")
        cash = int(portfolio.get_cash_balance().amount)
        assert cash > 0
```

**Exit criteria:** `python -m pytest tests/strategies/ tests/replay/ -v` passes. All tests green.

---

### Task E2: Certify SimulatedAdapter as paper adapter

**Files:**
- Modify: `src/titan/execution/simulated_adapter.py` (add adapter interface compliance)
- Create: `tests/adapters/__init__.py`
- Create: `tests/adapters/test_simulated_adapter_contract.py`
- Create: `docs/runbooks/paper-session.md`

**What to build:**

1. **`tests/adapters/test_simulated_adapter_contract.py`** — Adapter contract tests:

Exercise every scenario from FAILURE_MATRIX.md and Broker.spec.md:

- `test_submit_and_fill` — submit order with IMMEDIATE_FULL → status filled
- `test_submit_and_reject` — submit with REJECT → status rejected
- `test_submit_and_partial_fill` — PARTIAL_THEN_FULL → partially filled then tick → filled
- `test_submit_timeout` — TIMEOUT → stays pending (simulates UNKNOWN gateway)
- `test_never_fill` — NEVER_FILL → stays pending
- `test_cancel_pending_order` — cancel pending order → cancelled
- `test_cancel_filled_order_fails` — can't cancel already filled order
- `test_open_orders` — open orders tracked correctly
- `test_filled_orders` — filled orders tracked correctly
- `test_multiple_orders` — multiple orders tracked independently
- `test_get_order_nonexistent` — returns None

```python
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
        assert updated is None  # never advances

    def test_cancel_pending(self):
        order = self.adapter.submit_order("ord-6", "AAPL", "buy", 100, "150.00")
        assert order.status == "filled"  # immediate full
        # Pending cancel test
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
```

2. **`docs/runbooks/paper-session.md`** — Paper session runbook:

```markdown
# Paper Session Runbook

> **Purpose:** Operate a paper trading session using the SimulatedAdapter.
> **No real capital is at risk.**

## Prerequisites

- Python 3.14+ with titan package installed
- No broker credentials required (SimulatedAdapter is in-memory)

## Starting a session

```bash
python -m titan.cli risk status
# Expected: Trading state: Active, Kill switch: Armed
```

## Running the replay pipeline

```bash
python -m pytest tests/integration/test_paper_vertical_slice.py -v
```

## Kill switch drill

1. Trigger kill switch:
```python
from titan._core import RiskConfig, RiskGate
gate = RiskGate(RiskConfig(...))
gate.trigger_kill_switch()
```
2. Verify routing blocked: `gate.evaluate(intent)` returns rejected.
3. Release: `gate.release_initiated()` → `gate.release_completed()`
4. Verify routing resumes.

## Reconciliation drill

1. Apply fills to PortfolioEngine.
2. Create BrokerPosition with intentional drift.
3. Run ReconciliationEngine.compare() — verify drift detected.

## Session end

- Close all Python processes.
- Verify no state files remain.

## Incident response

If unexpected behavior occurs:
1. Halt: trigger kill switch.
2. Collect logs and state.
3. Document in knowledge/incidents/.
```

**Exit criteria:** `python -m pytest tests/adapters/ -v` passes. `python -m pytest tests/ -v` all pass.
