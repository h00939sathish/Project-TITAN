### Task C2c: Python simulated adapter + integration vertical slice test

**Files:**
- Create: `src/titan/execution/__init__.py` (empty package init)
- Create: `src/titan/execution/simulated_adapter.py` (simulated broker)
- Create: `tests/integration/test_paper_vertical_slice.py` (the big end-to-end test)

**What to build:**

1. **`src/titan/execution/__init__.py`** — empty package init, can just have a docstring.

2. **`src/titan/execution/simulated_adapter.py`** — SimulatedAdapter:

```python
"""Simulated broker adapter for deterministic paper trading."""

from dataclasses import dataclass
from enum import Enum
from titan._core import Money


class SimFillQuality(Enum):
    """Controls fill behavior for deterministic testing."""
    IMMEDIATE_FULL = "immediate_full"  # fill completely on first attempt
    PARTIAL_THEN_FULL = "partial_then_full"  # fill partially, then full on next check
    REJECT = "reject"  # reject the order
    TIMEOUT = "timeout"  # simulate timeout → UNKNOWN
    NEVER_FILL = "never_fill"  # stay pending forever


@dataclass
class SimOrderState:
    """Track a simulated order's lifecycle."""
    order_id: str
    instrument_id: str
    side: str
    quantity: int
    price: str
    status: str  # "pending", "partially_filled", "filled", "rejected"
    filled_quantity: int = 0
    fills: list = None
    
    def __post_init__(self):
        self.fills = self.fills or []


class SimulatedAdapter:
    """A deterministic simulated broker adapter for paper trading.
    
    Never connects to an external system. Controlled entirely by test code
    via `set_fill_quality()` and `tick()`.
    """
    
    def __init__(self):
        self._orders: dict[str, SimOrderState] = {}
        self._fill_quality: dict[str, SimFillQuality] = {}
        self._default_fill_quality = SimFillQuality.IMMEDIATE_FULL
        self._current_time = "2026-01-01T00:00:00Z"
    
    def set_default_fill_quality(self, quality: SimFillQuality):
        self._default_fill_quality = quality
    
    def set_fill_quality(self, order_id: str, quality: SimFillQuality):
        self._fill_quality[order_id] = quality
    
    def submit_order(self, order_id: str, instrument_id: str, side: str,
                     quantity: int, price: str) -> SimOrderState:
        """Submit an order and process according to fill quality."""
        quality = self._fill_quality.get(order_id, self._default_fill_quality)
        
        state = SimOrderState(
            order_id=order_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=price,
            status="pending",
        )
        
        if quality == SimFillQuality.REJECT:
            state.status = "rejected"
        elif quality == SimFillQuality.IMMEDIATE_FULL:
            self._apply_fill(state, quantity)
        elif quality == SimFillQuality.PARTIAL_THEN_FULL:
            self._apply_fill(state, quantity // 2)
        elif quality == SimFillQuality.TIMEOUT:
            state.status = "pending"  # stays pending (will be marked UNKNOWN externally)
        elif quality == SimFillQuality.NEVER_FILL:
            state.status = "pending"  # never fills
        
        self._orders[order_id] = state
        return state
    
    def tick(self, order_id: str) -> SimOrderState | None:
        """Advance time for a pending order. Returns updated order or None."""
        state = self._orders.get(order_id)
        if not state or state.status != "pending":
            return None
        
        quality = self._fill_quality.get(order_id, self._default_fill_quality)
        
        if quality == SimFillQuality.PARTIAL_THEN_FULL and state.filled_quantity > 0:
            remaining = state.quantity - state.filled_quantity
            self._apply_fill(state, remaining)
        
        return state
    
    def get_order(self, order_id: str) -> SimOrderState | None:
        return self._orders.get(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        state = self._orders.get(order_id)
        if state and state.status in ("pending", "partially_filled"):
            state.status = "cancelled"
            return True
        return False
    
    def _apply_fill(self, state: SimOrderState, quantity: int):
        state.filled_quantity += quantity
        fill_price = float(state.price) if state.price else 0.0
        state.fills.append({
            "time": self._current_time,
            "quantity": quantity,
            "price": fill_price,
        })
        if state.filled_quantity >= state.quantity:
            state.status = "filled"
        else:
            state.status = "partially_filled"
    
    @property
    def open_orders(self) -> list[SimOrderState]:
        return [o for o in self._orders.values() if o.status in ("pending", "partially_filled")]
    
    @property
    def filled_orders(self) -> list[SimOrderState]:
        return [o for o in self._orders.values() if o.status == "filled"]
```

3. **`tests/integration/test_paper_vertical_slice.py`** — the integration test:

```python
"""Full paper vertical slice: TradeIntent → Risk Decision → Execution → Fill → Portfolio → Reconciliation.

This is the crown-jewel test of Phase C. It proves the entire deterministic
pipeline works end-to-end.
"""

import pytest
from titan._core import (
    Money, RiskConfig, RiskGate, TradingState, KillSwitchState,
    TradeIntent, RiskReasonCode, PortfolioEngine, ReconciliationEngine,
    ReconciliationConfig, BrokerPosition, ReconciliationDriftSeverity,
)
from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality


@pytest.fixture
def default_config() -> RiskConfig:
    return RiskConfig(
        ["AAPL", "MSFT"],          # instrument_eligibility
        Money("50000", "USD"),      # max_order_notional
        1000,                       # max_order_quantity
        5000,                       # max_position_size
        Money("100000", "USD"),     # max_gross_exposure
        0.10,                       # max_drawdown_fraction
        Money("5000", "USD"),       # max_daily_loss
        5000,                       # data_freshness_threshold_ms
    )


@pytest.fixture
def gate(default_config) -> RiskGate:
    return RiskGate(default_config)


@pytest.fixture
def portfolio() -> PortfolioEngine:
    return PortfolioEngine("USD", Money("100000", "USD"))


@pytest.fixture
def adapter() -> SimulatedAdapter:
    return SimulatedAdapter()


def make_intent(instrument="AAPL", side="BUY", quantity="100",
                price="150", strategy_id="strat-v1") -> TradeIntent:
    return TradeIntent(
        strategy_id, "pkg-v1", "acct-1", instrument,
        side, quantity, "LIMIT", "DAY", "1.0",
        price=price,
    )


class TestPaperVerticalSlice:
    """Full pipeline: intent → risk → execution → fill → portfolio → reconciliation."""

    def test_happy_path(self, gate, portfolio, adapter):
        """A buy intent passes risk, executes, fills, updates portfolio, reconciles."""
        # 1. Strategy produces intent
        intent = make_intent(instrument="AAPL", side="BUY", quantity="100", price="150")
        
        # 2. Risk gate evaluates
        verdict = gate.evaluate(
            intent, 
            current_position_size=None,
            current_gross_exposure=None,
            current_drawdown=None,
            current_daily_loss=None,
        )
        assert verdict.accepted, f"Risk rejected: {verdict.reason_detail}"
        
        # 3. Simulated execution
        order = adapter.submit_order(
            order_id="ord-001",
            instrument_id=intent.instrument_id,
            side=intent.side.lower(),
            quantity=int(intent.quantity),
            price=intent.price or "0",
        )
        assert order.status == "filled"
        
        # 4. Apply fill to portfolio
        last_fill = order.fills[-1]
        portfolio.apply_fill(
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=last_fill["quantity"],
            price=Money(str(last_fill["price"]), "USD"),
        )
        
        # 5. Verify portfolio state
        pos = portfolio.get_position("AAPL")
        assert pos is not None
        assert pos.side.__str__() == "Long"  # PositionSide.Long
        assert pos.quantity == 100
        assert portfolio.get_cash_balance().amount == "85000"  # 100000 - 150*100
        
        # 6. Reconciliation
        reconciler = ReconciliationEngine()
        broker_position = BrokerPosition("AAPL", "LONG", 100)
        broker_cash = Money("85000", "USD")
        result = reconciler.compare(
            portfolio, [broker_position], broker_cash
        )
        assert result.severity == ReconciliationDriftSeverity.InSync

    def test_risk_rejects_intent(self, gate, portfolio, adapter):
        """Risk rejects an intent → no execution happens."""
        intent = make_intent(instrument="GOOGL")  # Not in eligible list
        verdict = gate.evaluate(intent, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.InstrumentNotEligible
        # Verify no order was submitted (nothing to test here — just proving the gate)

    def test_kill_switch_blocks_pipeline(self, gate, portfolio, adapter):
        """Kill switch triggered → all intents rejected."""
        gate.trigger_kill_switch()
        intent = make_intent()
        verdict = gate.evaluate(intent, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.KillSwitchTriggered

    def test_fill_updates_portfolio_correctly(self, portfolio):
        """Multiple fills compose correctly in portfolio."""
        portfolio.apply_fill("AAPL", "buy", 50, Money("100", "USD"))
        portfolio.apply_fill("AAPL", "buy", 50, Money("150", "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 100
        # Cost basis should be weighted average: (50*100 + 50*150) / 100 = 125
        # But due to integer division, it might be approximate
        assert portfolio.get_cash_balance().amount == "87500"  # 100000 - 5000 - 7500

    def test_partial_fill_then_full(self, gate, portfolio, adapter):
        """Partial fill followed by full fill is tracked correctly."""
        intent = make_intent(quantity="100", price="150")
        
        # Risk passes
        verdict = gate.evaluate(intent, None, None, None, None)
        assert verdict.accepted
        
        # Submit with partial fill quality
        order = adapter.submit_order(
            order_id="ord-002",
            instrument_id=intent.instrument_id,
            side=intent.side.lower(),
            quantity=int(intent.quantity),
            price=intent.price or "0",
        )
        assert order.status == "partially_filled"
        assert order.filled_quantity == 50
        
        # Apply partial fill
        portfolio.apply_fill("AAPL", "buy", 50, Money("150", "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 50
        
        # Tick the adapter to fill the rest
        updated = adapter.tick("ord-002")
        assert updated is not None
        assert updated.status == "filled"
        
        # Apply remaining fill
        last_fill = order.fills[-1]
        portfolio.apply_fill("AAPL", "buy", last_fill["quantity"],
                             Money(str(last_fill["price"]), "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 100
        assert portfolio.get_cash_balance().amount == "85000"

    def test_sell_then_reconcile(self, gate, portfolio):
        """Sell from portfolio and reconcile with broker."""
        # First buy
        portfolio.apply_fill("AAPL", "buy", 100, Money("150", "USD"))
        
        # Then sell 50 at a profit
        portfolio.apply_fill("AAPL", "sell", 50, Money("160", "USD"))
        
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 50
        assert pos.side.__str__() == "Long"
        
        # Check PnL
        assert portfolio.get_cash_balance().amount == "93000"  # 100000 - 15000 + 8000
        
        # Reconcile
        reconciler = ReconciliationEngine()
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 50)],
            Money("93000", "USD"),
        )
        assert result.severity == ReconciliationDriftSeverity.InSync

    def test_full_pipeline_with_rejection_then_recovery(self, gate, portfolio, adapter):
        """Rejected intent → fix → accepted → execute → reconcile."""
        # Step 1: Non-eligible instrument is rejected
        intent = make_intent(instrument="GOOGL")
        verdict = gate.evaluate(intent, None, None, None, None)
        assert not verdict.accepted
        
        # Step 2: Fix the intent
        intent = make_intent(instrument="AAPL", quantity="50", price="200")
        verdict = gate.evaluate(intent, None, None, None, None)
        assert verdict.accepted
        
        # Step 3: Execute
        order = adapter.submit_order("ord-003", "AAPL", "buy", 50, "200")
        assert order.status == "filled"
        
        # Step 4: Apply fill
        portfolio.apply_fill("AAPL", "buy", 50, Money("200", "USD"))
        
        # Step 5: Reconcile
        reconciler = ReconciliationEngine()
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 50)],
            Money("90000", "USD"),
        )
        assert result.severity == ReconciliationDriftSeverity.InSync

    def test_reconciliation_detects_drift(self, portfolio):
        """Reconciliation catches when broker state differs from portfolio."""
        portfolio.apply_fill("AAPL", "buy", 100, Money("100", "USD"))
        
        # Broker says we have 90, not 100
        reconciler = ReconciliationEngine(
            ReconciliationConfig(critical_drift_fraction=0.05)
        )
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 90)],
            Money("90000", "USD"),
        )
        # Drift: 10/100 = 10% > 5% → Critical
        assert result.severity == ReconciliationDriftSeverity.Critical
        assert len(result.position_drifts) == 1
        assert result.position_drifts[0].quantity_drift == 10

    def test_reconciliation_drift_warning(self, portfolio):
        """Small drift triggers warning, not critical."""
        portfolio.apply_fill("AAPL", "buy", 100, Money("100", "USD"))
        
        reconciler = ReconciliationEngine(
            ReconciliationConfig(critical_drift_fraction=0.10, warning_drift_fraction=0.01)
        )
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 98)],
            Money("90000", "USD"),
        )
        # Drift: 2/100 = 2% — between 1% warning and 10% critical
        assert result.severity == ReconciliationDriftSeverity.Warning

    def test_empty_portfolio_reconciles(self, portfolio):
        """Empty portfolio with no broker positions is in sync."""
        reconciler = ReconciliationEngine()
        result = reconciler.compare(portfolio, [], Money("100000", "USD"))
        assert result.severity == ReconciliationDriftSeverity.InSync
```

**Important notes:**
- Test file goes in `tests/integration/` — may need to create the directory
- Need `tests/integration/__init__.py` as well
- The test covers multiple scenarios: happy path, risk rejection, kill switch, partial fills, sell trades, recovery from rejection, and reconciliation drift detection
- Some test assertions may need adaptation based on actual Money string format (e.g., cash balance amounts)
- Money amounts are stored as strings, so comparisons use `.amount` attribute which is a string

**Run tests with:**
```bash
.venv\Scripts\python.exe -m pytest tests/integration/ -v
.venv\Scripts\python.exe -m pytest tests/ -v  # full suite
```

**Exit criteria:** All integration tests pass, full test suite still green (62+ tests).
