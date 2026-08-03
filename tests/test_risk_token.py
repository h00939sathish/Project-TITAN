import pytest
import uuid
import hashlib
from titan._core import ApprovedOrderIntent

def compute_risk_token(intent: ApprovedOrderIntent, secret_key: str) -> str:
    payload = f"{intent.risk_decision_id}:{intent.client_order_id}:{intent.instrument_id}:{intent.side}:{intent.quantity}:{intent.price or '0'}"
    return hashlib.sha256((secret_key + payload).encode('utf-8')).hexdigest()

def verify_risk_token(intent: ApprovedOrderIntent, secret_key: str, token: str) -> bool:
    expected = compute_risk_token(intent, secret_key)
    return token == expected


def test_approved_order_intent_token_signature_verification():
    intent = ApprovedOrderIntent(
        risk_decision_id=str(uuid.uuid4()),
        intent_id=str(uuid.uuid4()),
        client_order_id="test-client-1",
        instrument_id="SPY",
        side="BUY",
        quantity="100",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        price="450.00",
    )
    secret_key = "TITAN_SECRET_KEY_FOR_TESTING"
    token = compute_risk_token(intent, secret_key)

    assert verify_risk_token(intent, secret_key, token) is True
    assert verify_risk_token(intent, "WRONG_KEY", token) is False


def test_tampered_intent_fails_token_verification():
    intent = ApprovedOrderIntent(
        risk_decision_id=str(uuid.uuid4()),
        intent_id=str(uuid.uuid4()),
        client_order_id="test-client-2",
        instrument_id="SPY",
        side="BUY",
        quantity="100",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        price="450.00",
    )
    secret_key = "TITAN_SECRET_KEY_FOR_TESTING"
    valid_token = compute_risk_token(intent, secret_key)

    tampered_intent = ApprovedOrderIntent(
        risk_decision_id=intent.risk_decision_id,
        intent_id=intent.intent_id,
        client_order_id=intent.client_order_id,
        instrument_id=intent.instrument_id,
        side=intent.side,
        quantity="10000", # Tampered!
        order_type=intent.order_type,
        time_in_force=intent.time_in_force,
        risk_profile_version=intent.risk_profile_version,
        price=intent.price,
    )
    assert verify_risk_token(tampered_intent, secret_key, valid_token) is False
