import os
import pytest
from titan._core import EventEnvelope, TradeIntent, RiskDecision, ApprovedOrderIntent

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "contracts")

def read_fixture(filename: str) -> str:
    with open(os.path.join(FIXTURES_DIR, filename), "r") as f:
        return f.read()

def test_event_envelope_validation():
    valid = read_fixture("valid_event_envelope.json")
    env = EventEnvelope.from_json(valid)
    assert env.message_id == "018f0a0d-1234-7890-abcd-ef0123456789"

    invalid = read_fixture("invalid_event_envelope.json")
    with pytest.raises(ValueError, match="Deserialization error"):
        EventEnvelope.from_json(invalid)

def test_trade_intent_validation():
    valid = read_fixture("valid_trade_intent.json")
    intent = TradeIntent.from_json(valid)
    assert intent.strategy_id == "momentum-v1"
    assert intent.quantity == "1.5"
    assert intent.market_data_timestamp == "2026-07-13T23:12:00Z"

    invalid = read_fixture("invalid_trade_intent.json")
    with pytest.raises(ValueError, match="Deserialization error"):
        TradeIntent.from_json(invalid)

def test_risk_decision_validation():
    valid = read_fixture("valid_risk_decision.json")
    decision = RiskDecision.from_json(valid)
    assert decision.intent_id == "018f0a0d-1234-7890-abcd-ef0123456789"
    assert decision.decision == "ACCEPTED"

    invalid = read_fixture("invalid_risk_decision.json")
    with pytest.raises(ValueError, match="Deserialization error"):
        RiskDecision.from_json(invalid)

def test_approved_order_intent_validation():
    valid = read_fixture("valid_approved_order_intent.json")
    approved = ApprovedOrderIntent.from_json(valid)
    assert approved.risk_decision_id == "018f0a0d-1234-7890-abcd-ef0123456780"

    invalid = read_fixture("invalid_approved_order_intent.json")
    with pytest.raises(ValueError, match="Deserialization error"):
        ApprovedOrderIntent.from_json(invalid)
