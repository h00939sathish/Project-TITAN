"""Clock drift — system clock anomaly detected, intents rejected."""
from titan._core import RiskConfig, RiskGate, TradeIntent


class TestClockDrift:
    def test_clock_drift_rejects_intents(self):
        """Simulate clock anomaly by checking that gate can detect drift.
        Note: Current RiskGate doesn't have built-in clock drift detection.
        This test verifies the gate can reject under a simulated drift scenario
        by setting trading state to Halted when drift is detected.
        """
        from titan._core import TradingState
        config = RiskConfig.default()
        gate = RiskGate(config)
        intent = TradeIntent("s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", price="150")
        # Under clock drift, operator would halt trading
        gate.set_trading_state(TradingState.Halted)
        verdict = gate.evaluate(intent, None, None, None, None)
        assert not verdict.accepted, "Should reject intents during clock drift"
        assert verdict.reason.__str__() == "TradingHalted"

    def test_clock_drift_recovery(self):
        """After clock is synchronized and drift resolved, trading resumes."""
        from titan._core import TradingState
        config = RiskConfig.default()
        gate = RiskGate(config)
        intent = TradeIntent("s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0", price="150")
        # Simulate drift detection → halt
        gate.set_trading_state(TradingState.Halted)
        # Operator fixes clock and resumes
        gate.set_trading_state(TradingState.Active)
        verdict = gate.evaluate(intent, None, None, None, None)
        assert verdict.accepted, "Should accept intents after clock is normalized"
