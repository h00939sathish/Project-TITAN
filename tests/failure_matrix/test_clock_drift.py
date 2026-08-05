"""Clock drift — system clock anomaly detected via data staleness, intents rejected."""
from titan._core import RiskConfig, RiskGate, TradeIntent


class TestClockDrift:
    def test_stale_data_rejects_intent(self):
        """Market data timestamp older than threshold → DataStale rejection."""
        config = RiskConfig.default()
        gate = RiskGate(config)
        intent = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            "2020-01-01T00:00:00Z", price="150",
        )
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason.__str__() == "DataStale"

    def test_future_data_rejects_intent(self):
        """Market data timestamp too far in the future → DataStale rejection."""
        config = RiskConfig.default()
        gate = RiskGate(config)
        intent = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            "2099-12-31T23:59:59Z", price="150",
        )
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason.__str__() == "DataStale"

    def test_fresh_data_accepted(self):
        """Market data timestamp within threshold → accepted."""
        from datetime import datetime, timezone
        config = RiskConfig.default()
        gate = RiskGate(config)
        now = datetime.now(timezone.utc).isoformat()
        intent = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            now, price="150",
        )
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert verdict.accepted

    def test_clock_drift_rejects_intents(self):
        """After drift is detected and trading halted, intents are rejected."""
        from datetime import datetime, timezone
        from titan._core import TradingState
        config = RiskConfig.default()
        gate = RiskGate(config)
        intent = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            "2020-01-01T00:00:00Z", price="150",
        )
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert not verdict.accepted
        assert verdict.reason.__str__() == "DataStale"
        # Operator halts trading after drift detected
        gate.set_trading_state(TradingState.Halted)
        now = datetime.now(timezone.utc).isoformat()
        intent2 = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            now, price="150",
        )
        verdict2 = gate.evaluate(intent2, None, None, None, None, None)
        assert not verdict2.accepted
        assert verdict2.reason.__str__() == "TradingHalted"

    def test_clock_drift_recovery(self):
        """After clock is synchronized and trading resumes, intents accepted."""
        from titan._core import TradingState
        from datetime import datetime, timezone
        config = RiskConfig.default()
        gate = RiskGate(config)
        # Operator halts trading due to detected drift
        gate.set_trading_state(TradingState.Halted)
        # Operator fixes clock and resumes trading
        gate.set_trading_state(TradingState.Active)
        now = datetime.now(timezone.utc).isoformat()
        intent = TradeIntent(
            "s1", "p1", "a1", "AAPL", "BUY", "100", "LIMIT", "DAY", "1.0",
            now, price="150",
        )
        verdict = gate.evaluate(intent, None, None, None, None, None)
        assert verdict.accepted
