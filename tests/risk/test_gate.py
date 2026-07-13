"""Tests for risk gate from Python."""

from titan._core import (
    Money,
    RiskConfig,
    RiskGate,
    TradingState,
    KillSwitchState,
    TradeIntent,
    RiskVerdict,
    RiskReasonCode,
    PortfolioEngine,
)


def make_intent(instrument="AAPL", side="BUY", quantity="100", price="150") -> TradeIntent:
    return TradeIntent(
        "strat-v1", "abc123", "acct-1", instrument,
        side, quantity, "LIMIT", "DAY", "1.0",
        price=price,
    )


def make_default_gate() -> RiskGate:
    config = RiskConfig(
        [], Money("1000000", "USD"), 10000, 50000,
        Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000,
    )
    return RiskGate(config)


class TestRiskGate:
    def test_accepts_valid_intent(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted
        assert verdict.reason is None

    def test_rejects_when_kill_switch_triggered(self):
        gate = make_default_gate()
        gate.trigger_kill_switch()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.KillSwitchTriggered

    def test_rejects_when_trading_halted(self):
        gate = make_default_gate()
        gate.set_trading_state(TradingState.Halted)
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.TradingHalted

    def test_rejects_instrument_not_eligible(self):
        gate = RiskGate(
            RiskConfig(
                ["MSFT"], Money("1000000", "USD"), 10000, 50000,
                Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000,
            )
        )
        verdict = gate.evaluate(make_intent(instrument="AAPL"), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.InstrumentNotEligible

    def test_rejects_notional_exceeded(self):
        gate = RiskGate(
            RiskConfig(
                [], Money("100", "USD"), 10000, 50000,
                Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000,
            )
        )
        verdict = gate.evaluate(make_intent(quantity="10", price="50"), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.OrderNotionalExceeded

    def test_rejects_quantity_exceeded(self):
        gate = RiskGate(
            RiskConfig(
                [], Money("1000000", "USD"), 10, 50000,
                Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000,
            )
        )
        verdict = gate.evaluate(make_intent(quantity="100"), None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.OrderQuantityExceeded

    def test_rejects_position_size_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), 60000, None, None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.PositionLimitExceeded

    def test_rejects_gross_exposure_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, Money("20000000", "USD"), None, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.GrossExposureExceeded

    def test_rejects_drawdown_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, 0.50, None)
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.DrawdownExceeded

    def test_rejects_daily_loss_exceeded(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, Money("100000", "USD"))
        assert not verdict.accepted
        assert verdict.reason == RiskReasonCode.DailyLossExceeded

    def test_kill_switch_lifecycle(self):
        gate = make_default_gate()
        assert gate.kill_switch == KillSwitchState.Armed
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered
        gate.release_initiated()
        assert gate.kill_switch == KillSwitchState.Releasing
        gate.release_completed()
        assert gate.kill_switch == KillSwitchState.Released
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted

    def test_trading_state_lifecycle(self):
        gate = make_default_gate()
        assert gate.trading_state == TradingState.Active
        gate.set_trading_state(TradingState.Halted)
        assert gate.trading_state == TradingState.Halted
        gate.set_trading_state(TradingState.Active)
        assert gate.trading_state == TradingState.Active

    def test_portfolio_checks_skipped_when_none(self):
        gate = make_default_gate()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert verdict.accepted

    def test_risk_verdict_has_correct_fields(self):
        gate = make_default_gate()
        gate.trigger_kill_switch()
        verdict = gate.evaluate(make_intent(), None, None, None, None)
        assert hasattr(verdict, "accepted")
        assert hasattr(verdict, "reason")
        assert hasattr(verdict, "reason_detail")
        assert verdict.accepted is False
        assert verdict.reason is not None
        assert len(verdict.reason_detail) > 0

    def test_full_gate_to_portfolio_integration(self):
        gate = make_default_gate()
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        portfolio.apply_fill("AAPL", "buy", 100, Money("150", "USD"))
        snapshot = portfolio.get_snapshot()
        verdict = gate.evaluate(
            make_intent(quantity="50", price="160"),
            snapshot.position_size,
            snapshot.gross_exposure,
            snapshot.drawdown_fraction,
            snapshot.daily_realized_loss,
        )
        assert verdict.accepted
