"""Tests for canonical message types (EventEnvelope, TradeIntent, RiskDecision)."""

from titan._core import ApprovedOrderIntent, EventEnvelope, RiskDecision, TradeIntent


class TestEventEnvelope:
    def test_create_minimal(self) -> None:
        env = EventEnvelope("test.event", "test", "id-1", "test-service", '{"key": "val"}')
        assert env.message_type == "test.event"
        assert env.aggregate_type == "test"
        assert env.aggregate_id == "id-1"
        assert env.source == "test-service"
        assert env.payload == '{"key": "val"}'
        assert env.message_id is not None
        assert env.correlation_id is not None
        assert env.causation_id is None
        assert env.metadata is None

    def test_create_with_all_fields(self) -> None:
        env = EventEnvelope(
            "order.filled",
            "order",
            "ORD-001",
            "execution",
            '{"qty": "100"}',
            correlation_id="corr-1",
            causation_id="cause-1",
            metadata='{"config_digest": "abc"}',
        )
        assert env.correlation_id == "corr-1"
        assert env.causation_id == "cause-1"
        assert env.metadata == '{"config_digest": "abc"}'

    def test_round_trip_json(self) -> None:
        env = EventEnvelope("test.event", "test", "id-1", "svc", '{"n": 42}')
        json_str = env.to_json()
        restored = EventEnvelope.from_json(json_str)
        assert restored.message_id == env.message_id
        assert restored.message_type == env.message_type
        assert restored.aggregate_id == env.aggregate_id
        assert restored.payload == env.payload
        assert restored.source == env.source

    def test_rejects_invalid_json(self) -> None:
        try:
            EventEnvelope.from_json("{invalid}")
            assert False, "Should have raised"
        except Exception:
            pass


class TestTradeIntent:
    def test_create_minimal(self) -> None:
        intent = TradeIntent(
            "strat-1", "abc123", "acc-1", "AAPL.NASDAQ",
            "BUY", "100", "MARKET", "DAY", "1.0", "2026-07-13T23:12:00Z"
        )
        assert intent.strategy_id == "strat-1"
        assert intent.side == "BUY"
        assert intent.quantity == "100"
        assert intent.order_type == "MARKET"
        assert intent.price is None

    def test_create_with_limit(self) -> None:
        intent = TradeIntent(
            "strat-1", "abc123", "acc-1", "AAPL.NASDAQ",
            "SELL", "200", "LIMIT", "GTC", "1.0", "2026-07-13T23:12:00Z",
            price="150.50",
        )
        assert intent.side == "SELL"
        assert intent.price == "150.50"
        assert intent.order_type == "LIMIT"
        assert intent.time_in_force == "GTC"

    def test_round_trip_json(self) -> None:
        intent = TradeIntent(
            "s1", "d1", "a1", "AAPL", "BUY", "50", "MARKET", "DAY", "1.0", "2026-07-13T23:12:00Z",
        )
        json_str = intent.to_json()
        restored = TradeIntent.from_json(json_str)
        assert restored.strategy_id == intent.strategy_id
        assert restored.side == intent.side
        assert restored.quantity == intent.quantity


class TestRiskDecision:
    def test_accepted(self) -> None:
        decision = RiskDecision(
            "018f0a0d-1234-7890-abcd-ef0123456789", "ACCEPTED", [], '[]',
        )
        assert decision.decision == "ACCEPTED"
        assert decision.reason_codes == []
        assert decision.evaluated_at is not None

    def test_rejected(self) -> None:
        decision = RiskDecision(
            "018f0a0d-1234-7890-abcd-ef0123456789", "REJECTED",
            ["PRICE_CHECK_FAIL", "POSITION_LIMIT_EXCEEDED"],
            '[{"rule": "price_check", "result": "FAIL"}]',
        )
        assert decision.decision == "REJECTED"
        assert len(decision.reason_codes) == 2

    def test_round_trip_json(self) -> None:
        d = RiskDecision("018f0a0d-1234-7890-abcd-ef0123456789", "ACCEPTED", [], '[]')
        json_str = d.to_json()
        restored = RiskDecision.from_json(json_str)
        assert restored.decision == d.decision
        assert restored.intent_id == d.intent_id


class TestApprovedOrderIntent:
    def test_create(self) -> None:
        approved = ApprovedOrderIntent(
            "018f0a0d-1234-7890-abcd-ef0123456780", "018f0a0d-1234-7890-abcd-ef0123456789", "018f0a0d-1234-7890-abcd-ef0123456781", "AAPL.NASDAQ",
            "BUY", "100", "MARKET", "DAY", "1.0",
        )
        assert approved.client_order_id == "018f0a0d-1234-7890-abcd-ef0123456781"
        assert approved.side == "BUY"
        assert approved.risk_decision_id == "018f0a0d-1234-7890-abcd-ef0123456780"
