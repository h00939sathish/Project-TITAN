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
        ["AAPL", "MSFT"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
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
    from datetime import datetime, timezone
    return TradeIntent(
        strategy_id, "pkg-v1", "acct-1", instrument,
        side, quantity, "LIMIT", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        price=price,
    )


class TestPaperVerticalSlice:
    """Full pipeline: intent -> risk -> execution -> fill -> portfolio -> reconciliation."""

    def test_happy_path(self, gate, portfolio, adapter):
        """A buy intent passes risk, executes, fills, updates portfolio, reconciles."""
        intent = make_intent(instrument="AAPL", side="BUY", quantity="100", price="150")

        verdict = gate.evaluate(
            intent,
            current_position_size=None,
            current_gross_exposure=None,
            current_drawdown=None,
            current_daily_loss=None,
            current_position_side=None,
        )
        assert verdict.accepted, f"Risk rejected: {verdict.reason_detail}"

        order = adapter.submit_order(
            order_id="ord-001",
            instrument_id=intent.instrument_id,
            side=intent.side.lower(),
            quantity=int(intent.quantity),
            price=intent.price or "0",
        )
        assert order.status == "filled"

        last_fill = order.fills[-1]
        portfolio.apply_fill(
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=last_fill["quantity"],
            price=Money(order.price, "USD"),
        )

        pos = portfolio.get_position("AAPL")
        assert pos is not None
        assert pos.side.__str__() == "Long"
        assert pos.quantity == 100
        assert portfolio.get_cash_balance().amount == "85000"

        reconciler = ReconciliationEngine()
        broker_position = BrokerPosition("AAPL", "LONG", 100)
        broker_cash = Money("85000", "USD")
        result = reconciler.compare(
            portfolio, [broker_position], broker_cash
        )
        assert result.severity == ReconciliationDriftSeverity.InSync

    def test_risk_rejects_intent(self, gate, portfolio, adapter):
        """Risk rejects an intent -> no execution happens."""
        intent = make_intent(instrument="GOOGL")
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.InstrumentNotEligible

    def test_kill_switch_blocks_pipeline(self, gate, portfolio, adapter):
        """Kill switch triggered -> all intents rejected."""
        gate.trigger_kill_switch()
        intent = make_intent()
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.KillSwitchTriggered

    def test_fill_updates_portfolio_correctly(self, portfolio):
        """Multiple fills compose correctly in portfolio."""
        portfolio.apply_fill("AAPL", "buy", 50, Money("100", "USD"))
        portfolio.apply_fill("AAPL", "buy", 50, Money("150", "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 100
        assert portfolio.get_cash_balance().amount == "87500"

    def test_partial_fill_then_full(self, gate, portfolio, adapter):
        """Partial fill followed by full fill is tracked correctly."""
        intent = make_intent(quantity="100", price="150")

        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert verdict.accepted

        adapter.set_default_fill_quality(SimFillQuality.PARTIAL_THEN_FULL)
        order = adapter.submit_order(
            order_id="ord-002",
            instrument_id=intent.instrument_id,
            side=intent.side.lower(),
            quantity=int(intent.quantity),
            price=intent.price or "0",
        )
        assert order.status == "partially_filled"
        assert order.filled_quantity == 50

        portfolio.apply_fill("AAPL", "buy", 50, Money("150", "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 50

        updated = adapter.tick("ord-002")
        assert updated is not None
        assert updated.status == "filled"

        last_fill = order.fills[-1]
        portfolio.apply_fill("AAPL", "buy", last_fill["quantity"],
                             Money(str(int(last_fill["price"])), "USD"))
        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 100
        assert portfolio.get_cash_balance().amount == "85000"

    def test_sell_then_reconcile(self, gate, portfolio):
        """Sell from portfolio and reconcile with broker."""
        portfolio.apply_fill("AAPL", "buy", 100, Money("150", "USD"))

        portfolio.apply_fill("AAPL", "sell", 50, Money("160", "USD"))

        pos = portfolio.get_position("AAPL")
        assert pos.quantity == 50
        assert pos.side.__str__() == "Long"

        assert portfolio.get_cash_balance().amount == "93000"

        reconciler = ReconciliationEngine()
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 50)],
            Money("93000", "USD"),
        )
        assert result.severity == ReconciliationDriftSeverity.InSync

    def test_full_pipeline_with_rejection_then_recovery(self, gate, portfolio, adapter):
        """Rejected intent -> fix -> accepted -> execute -> reconcile."""
        intent = make_intent(instrument="GOOGL")
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted

        intent = make_intent(instrument="AAPL", quantity="50", price="200")
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert verdict.accepted

        order = adapter.submit_order("ord-003", "AAPL", "buy", 50, "200")
        assert order.status == "filled"

        portfolio.apply_fill("AAPL", "buy", 50, Money("200", "USD"))

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

        reconciler = ReconciliationEngine(
            ReconciliationConfig(critical_drift_fraction=0.05)
        )
        result = reconciler.compare(
            portfolio,
            [BrokerPosition("AAPL", "LONG", 90)],
            Money("90000", "USD"),
        )
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
        assert result.severity == ReconciliationDriftSeverity.Warning

    def test_empty_portfolio_reconciles(self, portfolio):
        """Empty portfolio with no broker positions is in sync."""
        reconciler = ReconciliationEngine()
        result = reconciler.compare(portfolio, [], Money("100000", "USD"))
        assert result.severity == ReconciliationDriftSeverity.InSync
