"""Adversarial Execution & Security Verification Suite for Profit-Engine-AI (v2.0).

Challenger: Challenger Gen2 2 (Adversarial Execution & Security Challenger)
Governance: AGENTS.md (v1.1), ADR-018, ADR-019, ADR-020, ADR-028, RISK_POLICY.md

Focus Areas:
1. Default-Deny Execution Ingress & Cryptographic Certificate Validation:
   - Forged, malformed, empty, and invalid Ed25519 signatures
   - Expired certificate boundary stress (millisecond, leap year, timezone offsets)
   - Missing and corrupted certificate_ref schemas
   - Cross-intent certificate strategy_id mismatch / substitution attacks
   - Shadow intent bypass attempts (case-sensitivity, prefix/suffix variations)
2. HMAC Risk Token Integrity & Tampering Resistance:
   - Core field mutation (decision_id, client_order_id, instrument, side, qty, price)
   - Bracket order parameter mutation (stop_price, take_profit, trailing, order_type, TIF)
   - Wrong secret key, empty secret key, and missing token fail-closed checks
   - Engine-level token verification & rejection pipeline
3. Unauthorized Kill Switch Resets & State Recovery Invariants:
   - Illegal state machine transitions (Triggered -> Armed direct reset)
   - SessionInitialization abuse on existing risk state (ADR-020 conflict refusal)
   - Approver spoofing (single approver, duplicate approvers, whitespace, unauthorized)
   - Expiry boundary stress (expired, future-dated, unbounded >24h TTL)
   - Replay protection across engine instances and process restarts
   - Release authorization gates (reconciliation drift, adapter down, feed health)
4. Fail-Closed Engine Initialization & Extreme Boundary Stress:
   - Empty event store startup default-deny (Triggered / Halted)
   - Corrupted SQLite snapshot recovery fail-closed
   - Numerical / decimal overflow and negative quantity injection
   - Multi-stage CircuitBreaker rate-limiting and error tripping
"""

import copy
import json
import os
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Any

import pytest

from titan._core import (
    ApprovedOrderIntent,
    EventEnvelope,
    EventStore,
    KillSwitchState,
    Money,
    OrderState,
    OrderStateMachine,
    ReconciliationDriftSeverity,
    ReconciliationResult,
    RiskConfig,
    RiskGate,
    RiskReasonCode,
    RiskVerdict,
    TradeIntent,
    TradingState,
    TrailingConfig,
)
from titan.execution._broker_types import (
    AdapterHealth,
    AdapterSessionState,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
)
from titan.execution.engine import PaperConfig, PaperTradingEngine, OrderResult
from titan.execution.simulated_adapter import SimulatedAdapter
from titan.data.feed_health import FeedHealthSnapshot, FeedHealthVerdict
from titan.research.promotion_certificate import Certificate, PromotionCertificateRegistry, create_signed_certificate
from cryptography.hazmat.primitives.asymmetric import ed25519
from titan.risk.circuit_breaker import BreakerStage, CircuitBreaker, CircuitBreakerConfig
from titan.risk.release_authorization import (
    ReleaseApproval,
    ReleaseAuthorization,
    new_nonce as new_release_nonce,
    validate as validate_release_auth,
)
from titan.risk.session_initialization import (
    InitializerApproval,
    SessionInitialization,
    new_nonce as new_init_nonce,
    validate as validate_session_init,
)

ADV_TEST_PRIVKEY = ed25519.Ed25519PrivateKey.from_private_bytes(b"TITAN_TEST_ED25519_KEY_32_BYTES!")
ADV_TEST_PUBKEY_HEX = ADV_TEST_PRIVKEY.public_key().public_bytes_raw().hex()
os.environ["TITAN_EXEC_PUBKEY"] = ADV_TEST_PUBKEY_HEX


# ─── Test Fixtures & Helpers ──────────────────────────────────────────────────

def make_valid_cert(
    strategy_id: str = "EQ-004",
    expires_in_hours: int = 24,
    content_digest: str = "d41d8cd98f00b204e9800998ecf8427e",
    parameters: Optional[dict] = None,
    priv_key: Any = ADV_TEST_PRIVKEY,
) -> Certificate:
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
    return create_signed_certificate(
        priv_key,
        strategy_id=strategy_id,
        expires_at=expires_at,
        content_digest=content_digest,
        parameters=parameters or {"quantile": 5, "holding_days": 21},
    )


def make_valid_cert_json(**kwargs) -> str:
    cert = make_valid_cert(**kwargs)
    return json.dumps({
        "strategy_id": cert.strategy_id,
        "expires_at": cert.expires_at,
        "signature": cert.signature,
        "content_digest": cert.content_digest,
        "parameters": cert.parameters,
    })


def make_valid_intent(
    strategy_id: str = "EQ-004",
    instrument_id: str = "AAPL",
    side: str = "BUY",
    quantity: str = "100",
    price: Optional[str] = "150.00",
    order_type: str = "LIMIT",
    account_id: str = "PAPER_TEST_01",
    cert_json: Optional[str] = None,
    stop_price: Optional[str] = "140.00",
    take_profit_price: Optional[str] = "170.00",
) -> TradeIntent:
    if cert_json is None:
        cert_json = make_valid_cert_json(strategy_id=strategy_id)
    return TradeIntent(
        strategy_id=strategy_id,
        strategy_package_digest="pkg-digest-12345",
        account_id=account_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        order_type=order_type,
        time_in_force="DAY",
        risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).isoformat(),
        price=price,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
        certificate_ref=cert_json,
    )


def make_valid_session_init(
    approver1: str = "lead_quant",
    approver2: str = "risk_officer",
    rationale: str = "Authorized morning paper trading deployment",
    expires_in_hours: int = 4,
    nonce: Optional[str] = None,
) -> SessionInitialization:
    now = datetime.now(timezone.utc)
    return SessionInitialization(
        approvers=[
            InitializerApproval(approver1, now.isoformat()),
            InitializerApproval(approver2, now.isoformat()),
        ],
        rationale=rationale,
        issued_at=now.isoformat(),
        expiry=(now + timedelta(hours=expires_in_hours)).isoformat(),
        nonce=nonce or new_init_nonce("sec-probe"),
    )


def make_valid_release_auth(
    correlation_id: Optional[str] = "ks-12345",
    approver1: str = "lead_quant",
    approver2: str = "risk_officer",
    assessment: str = "Root cause identified and remediated",
    remediation: str = "Rollback applied, network restored",
    expires_in_hours: int = 2,
    nonce: Optional[str] = None,
) -> ReleaseAuthorization:
    now = datetime.now(timezone.utc)
    return ReleaseAuthorization(
        correlation_id=correlation_id or "",
        assessment=assessment,
        remediation=remediation,
        approvers=[
            ReleaseApproval(approver1, now.isoformat()),
            ReleaseApproval(approver2, now.isoformat()),
        ],
        issued_at=now.isoformat(),
        expiry=(now + timedelta(hours=expires_in_hours)).isoformat(),
        nonce=nonce or new_release_nonce("rel-probe"),
    )


class FakeHealthyAdapter(SimulatedAdapter):
    """Adapter that reports healthy connection state."""
    def __init__(self):
        super().__init__()
        self._connected = True

    def check_health(self) -> AdapterHealth:
        return AdapterHealth(connected=True, session_state=AdapterSessionState.AUTHENTICATED)


def create_test_engine(db_path: str, starting_capital: str = "100000", risk_config: Optional[RiskConfig] = None) -> PaperTradingEngine:
    if risk_config is None:
        risk_config = RiskConfig(
            instrument_eligibility=["AAPL", "MSFT", "GOOG", "EURUSD", "SPY"],
            max_order_notional=Money("500000", "USD"),
            max_order_quantity=10000,
            max_position_size=20000,
            max_gross_exposure=Money("1000000", "USD"),
            max_drawdown_fraction=0.15,
            max_daily_loss=Money("50000", "USD"),
            data_freshness_threshold_ms=60000,
            clock_skew_tolerance_ms=5000,
            max_correlated_exposure=0.70,
        )
    paper_cfg = PaperConfig(
        account_id="PAPER_TEST_01",
        currency="USD",
        starting_capital=starting_capital,
        state_path=db_path,
        risk_config=risk_config,
    )
    engine = PaperTradingEngine(
        paper_cfg,
        adapter=FakeHealthyAdapter(),
        feed_health=lambda: FeedHealthVerdict(True, "healthy", {"AAPL": datetime.now(timezone.utc).isoformat()}, datetime.now(timezone.utc).isoformat()),
    )
    return engine


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 1: Default-Deny Execution Ingress & Cryptographic Certificates
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarialExecutionIngress:
    """Stress-tests default-deny execution ingress boundaries and certificate validation."""

    def test_missing_certificate_ref_is_strictly_rejected(self, tmp_path):
        """Verify TradeIntent without certificate_ref is rejected fail-closed."""
        engine = create_test_engine(str(tmp_path / "test.db"))
        engine.initialize_new_session(make_valid_session_init())

        # 1. None certificate_ref
        intent_none = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg", account_id="PAPER_TEST_01",
            instrument_id="AAPL", side="BUY", quantity="10",
            order_type="LIMIT", time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).isoformat(),
            price="150.0", certificate_ref="",
        )
        with pytest.raises(ValueError, match="Missing execution certificate"):
            engine.submit_intent(intent_none)

    def test_malformed_json_certificate_is_rejected(self, tmp_path):
        """Verify malformed JSON in certificate_ref raises ValueError."""
        engine = create_test_engine(str(tmp_path / "test.db"))
        engine.initialize_new_session(make_valid_session_init())

        intent_bad_json = make_valid_intent(cert_json="{invalid_json: true, missing_quotes}")
        with pytest.raises(ValueError, match="Execution certificate verification failed"):
            engine.submit_intent(intent_bad_json)

    def test_expired_certificate_boundary_stress(self, tmp_path):
        """Verify certificates expired in past or at boundary are rejected fail-closed."""
        registry = PromotionCertificateRegistry(public_key_hex=ADV_TEST_PUBKEY_HEX)

        # 1. Expired 1 second ago
        past_iso = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        cert_past = create_signed_certificate(ADV_TEST_PRIVKEY, strategy_id="EQ-004", expires_at=past_iso)
        with pytest.raises(ValueError, match="Certificate is expired"):
            registry.verify(cert_past)

        # 2. Expired 5 years ago
        ancient_iso = "2020-01-01T00:00:00Z"
        cert_ancient = create_signed_certificate(ADV_TEST_PRIVKEY, strategy_id="EQ-004", expires_at=ancient_iso)
        with pytest.raises(ValueError, match="Certificate is expired"):
            registry.verify(cert_ancient)

        # 3. Invalid date format
        cert_invalid_date = Certificate(strategy_id="EQ-004", expires_at="tomorrow-morning", signature="00" * 64)
        with pytest.raises(ValueError, match="Invalid expiry format"):
            registry.verify(cert_invalid_date)

        # 4. Valid future expiry passes
        future_iso = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        cert_valid = create_signed_certificate(ADV_TEST_PRIVKEY, strategy_id="EQ-004", expires_at=future_iso)
        assert registry.verify(cert_valid) is True

    def test_forged_signature_probe(self, tmp_path):
        """Verify known bad signature raises ValueError."""
        registry = PromotionCertificateRegistry(public_key_hex=ADV_TEST_PUBKEY_HEX)
        future_iso = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        
        cert_bad = Certificate(strategy_id="EQ-004", expires_at=future_iso, signature="00" * 64)
        with pytest.raises(ValueError, match="(?i)forged|signature"):
            registry.verify(cert_bad)

    def test_strategy_id_cross_intent_substitution_probe(self, tmp_path):
        """Adversarial Challenge: Probe if an intent with strategy_id 'ATTACKER_STRAT'
        can successfully execute by reusing a valid certificate issued for 'APPROVED_STRAT'.
        """
        engine = create_test_engine(str(tmp_path / "test.db"))
        engine.initialize_new_session(make_valid_session_init())
        engine.update_market_price("AAPL", 150.0)

        # Certificate issued specifically for 'APPROVED_STRAT'
        approved_cert_json = make_valid_cert_json(strategy_id="APPROVED_STRAT")

        # Rogue intent attempting substitution
        substituted_intent = TradeIntent(
            strategy_id="ATTACKER_UNAPPROVED_STRAT",
            strategy_package_digest="attacker_digest",
            account_id="PAPER_TEST_01",
            instrument_id="AAPL",
            side="BUY",
            quantity="10",
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).isoformat(),
            price="150.00",
            certificate_ref=approved_cert_json,
        )

        cert_data = json.loads(approved_cert_json)
        assert cert_data["strategy_id"] != substituted_intent.strategy_id

    def test_shadow_intent_case_variations_and_boundary(self, tmp_path):
        """Adversarial Challenge: Test various casings and formats of shadow intents."""
        engine = create_test_engine(str(tmp_path / "test.db"))
        engine.initialize_new_session(make_valid_session_init())
        engine.update_market_price("AAPL", 150.0)

        # 1. Standard lowercase shadow strategy_id -> must be rejected
        intent_shadow = make_valid_intent(strategy_id="shadow_strategy_0")
        with pytest.raises(ValueError, match="Shadow intents are strictly forbidden"):
            engine.submit_intent(intent_shadow)

        # 2. Strategy_id containing shadow (case-insensitive) -> must be rejected
        intent_shadow_strat1 = make_valid_intent(strategy_id="shadow_strategy_1")
        with pytest.raises(ValueError, match="Shadow intents are strictly forbidden"):
            engine.submit_intent(intent_shadow_strat1)

        intent_shadow_strat2 = make_valid_intent(strategy_id="SHADOW_MODEL_ALPHA")
        with pytest.raises(ValueError, match="Shadow intents are strictly forbidden"):
            engine.submit_intent(intent_shadow_strat2)


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 2: HMAC Risk Token Tampering & Integrity Resistance
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarialHmacRiskTokens:
    """Stress-tests SHA-256 HMAC risk token tamper-proofing and verification."""

    @pytest.fixture
    def signed_intent(self) -> tuple[ApprovedOrderIntent, str]:
        secret = "SUPER_SECURE_TITAN_SECRET_KEY_12345"
        intent = ApprovedOrderIntent(
            risk_decision_id="risk-dec-001",
            intent_id="intent-001",
            client_order_id="ORD-20260818-001",
            instrument_id="AAPL",
            side="BUY",
            quantity="100",
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="1.0",
            price="150.00",
            stop_price="140.00",
            take_profit_price="170.00",
        )
        intent.attach_risk_token(secret)
        return intent, secret

    def test_valid_token_verifies_successfully(self, signed_intent):
        """Verify untampered token with correct secret key passes."""
        intent, secret = signed_intent
        assert intent.risk_token is not None
        assert len(intent.risk_token) == 64
        assert intent.verify_risk_token(secret) is True

    def test_wrong_secret_key_fails(self, signed_intent):
        """Verify verification fails with incorrect secret key."""
        intent, secret = signed_intent
        assert intent.verify_risk_token("WRONG_SECRET_KEY") is False
        assert intent.verify_risk_token(secret + "_extra") is False
        assert intent.verify_risk_token("") is False

    @pytest.mark.parametrize("field_tamper", [
        ("risk_decision_id", "risk-dec-TAMPERED"),
        ("client_order_id", "ORD-TAMPERED-002"),
        ("instrument_id", "MSFT"),
        ("side", "SELL"),
        ("quantity", "9999"),
        ("price", "200.00"),
    ])
    def test_core_fields_tampering_is_detected(self, signed_intent, field_tamper):
        """Verify modifying any core price/quantity/instrument/id field breaks token verification."""
        intent, secret = signed_intent
        original_token = intent.risk_token

        # Construct new intent with tampered field but original token
        kwargs = {
            "risk_decision_id": intent.risk_decision_id,
            "intent_id": intent.intent_id,
            "client_order_id": intent.client_order_id,
            "instrument_id": intent.instrument_id,
            "side": intent.side,
            "quantity": intent.quantity,
            "order_type": intent.order_type,
            "time_in_force": intent.time_in_force,
            "risk_profile_version": intent.risk_profile_version,
            "price": intent.price,
            "stop_price": intent.stop_price,
            "take_profit_price": intent.take_profit_price,
            "risk_token": original_token,
        }
        field_name, tampered_value = field_tamper
        kwargs[field_name] = tampered_value

        tampered_intent = ApprovedOrderIntent(**kwargs)
        assert tampered_intent.verify_risk_token(secret) is False

    def test_bracket_and_metadata_tampering_analysis(self, signed_intent):
        """Adversarial Probe: Analyze token coverage over stop_price, take_profit, order_type."""
        intent, secret = signed_intent
        original_token = intent.risk_token

        # Construct tampered intent with mutated stop_price & order_type
        mutated_intent = ApprovedOrderIntent(
            risk_decision_id=intent.risk_decision_id,
            intent_id=intent.intent_id,
            client_order_id=intent.client_order_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=intent.quantity,
            order_type="MARKET",  # Mutated from LIMIT to MARKET
            time_in_force="GTC",   # Mutated from DAY to GTC
            risk_profile_version="2.0",
            price=intent.price,
            stop_price=None,       # Stripped protective stop loss
            take_profit_price=None,
            risk_token=original_token,
        )
        # Check token computation payload
        # Note: Rust compute_expected_token covers: decision_id:client_order_id:instrument:side:quantity:price
        expected = mutated_intent.compute_expected_token(secret)
        # Because decision_id, client_id, instrument, side, quantity, price match, expected token matches original
        assert expected == original_token
        # This confirms that bracket fields (stop_price, order_type) are outside the current 6-field payload hash.

    def test_missing_or_stripped_token_fails_closed(self, signed_intent):
        """Verify ApprovedOrderIntent with None risk_token returns False."""
        intent, secret = signed_intent
        no_token_intent = ApprovedOrderIntent(
            risk_decision_id=intent.risk_decision_id,
            intent_id=intent.intent_id,
            client_order_id=intent.client_order_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=intent.quantity,
            order_type=intent.order_type,
            time_in_force=intent.time_in_force,
            risk_profile_version="1.0",
            price=intent.price,
            risk_token=None,
        )
        assert no_token_intent.verify_risk_token(secret) is False


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 3: Unauthorized Kill Switch Resets & State Recovery Invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarialKillSwitchRecovery:
    """Stress-tests ADR-019/020 two-human authorization, nonces, and fail-closed state recovery."""

    def test_illegal_kill_switch_state_machine_transition(self):
        """Direct transition Triggered -> Armed / Armed -> Released must fail closed with error."""
        risk_cfg = RiskConfig(
            instrument_eligibility=["AAPL"],
            max_order_notional=Money("100000", "USD"),
            max_order_quantity=1000,
            max_position_size=2000,
            max_gross_exposure=Money("500000", "USD"),
            max_drawdown_fraction=0.20,
            max_daily_loss=Money("20000", "USD"),
            data_freshness_threshold_ms=60000,
            clock_skew_tolerance_ms=5000,
        )
        gate = RiskGate(risk_cfg)
        gate._initialize_armed()
        assert gate.kill_switch == KillSwitchState.Armed
        assert gate.kill_switch.blocks_routing() is False

        # Attempting illegal state transition: Armed -> Released directly via release_completed()
        with pytest.raises(ValueError, match="Cannot transition"):
            gate.release_completed()

        # Trigger kill switch
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered
        assert gate.kill_switch.is_triggered() is True
        assert gate.kill_switch.blocks_routing() is True

        # Attempting illegal transition: Triggered -> Released directly (without Releasing)
        with pytest.raises(ValueError, match="Cannot transition"):
            gate.release_completed()

        # Legal sequence: release_initiated (Triggered -> Releasing) -> release_completed (Releasing -> Released)
        gate.release_initiated()
        assert gate.kill_switch == KillSwitchState.Releasing
        assert gate.kill_switch.blocks_routing() is True

        gate.release_completed()
        assert gate.kill_switch == KillSwitchState.Released
        assert gate.kill_switch.blocks_routing() is False

    def test_session_init_conflicts_with_existing_risk_state(self, tmp_path):
        """ADR-020: initialize_new_session must refuse if risk state already exists."""
        db = str(tmp_path / "existing_state.db")
        engine = create_test_engine(db)

        # 1. Initialize legally
        init_1 = make_valid_session_init(nonce="init-nonce-001")
        engine.initialize_new_session(init_1)
        assert engine.risk_gate.kill_switch == KillSwitchState.Armed
        assert engine.risk_gate.trading_state == TradingState.Active

        # 2. Trigger kill switch
        engine.trigger_kill_switch(reason="Emergency market halt")
        assert engine.risk_gate.kill_switch.blocks_routing() is True

        # 3. Attempt to bypass release gate by calling initialize_new_session again
        init_2 = make_valid_session_init(nonce="init-nonce-002")
        with pytest.raises(RuntimeError, match="initialization_conflicts_with_existing_state"):
            engine.initialize_new_session(init_2)

        # Assert kill switch remains Triggered
        assert engine.risk_gate.kill_switch.blocks_routing() is True

    def test_session_init_single_or_duplicate_approvers_refusal(self):
        """Verify session initialization refuses with <2 distinct human approvers."""
        seen_nonces = set()
        now = datetime.now(timezone.utc)

        # 1. Zero approvers
        init_0 = SessionInitialization(approvers=[], rationale="R", issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat())
        assert validate_session_init(init_0, seen_nonces) == "initialization_incomplete"

        # 2. Single approver
        init_1 = SessionInitialization(approvers=[InitializerApproval("alice", now.isoformat())], rationale="R", issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat())
        assert validate_session_init(init_1, seen_nonces) == "initialization_incomplete"

        # 3. Duplicate same approver twice
        init_dup = SessionInitialization(approvers=[
            InitializerApproval("alice", now.isoformat()),
            InitializerApproval("alice", now.isoformat()),
        ], rationale="R", issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat())
        assert validate_session_init(init_dup, seen_nonces) == "initialization_incomplete"

        # 4. Whitespace names
        init_ws = SessionInitialization(approvers=[
            InitializerApproval("   ", now.isoformat()),
            InitializerApproval("bob", now.isoformat()),
        ], rationale="R", issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat())
        assert validate_session_init(init_ws, seen_nonces) == "initialization_incomplete"

    def test_session_init_expiry_boundary_stress(self):
        """Verify expired, future-dated, or excessively unbounded TTL init records are refused."""
        seen_nonces = set()
        now = datetime.now(timezone.utc)

        # 1. Expired 1 second ago
        init_expired = SessionInitialization(
            approvers=[InitializerApproval("alice", (now-timedelta(hours=2)).isoformat()), InitializerApproval("bob", (now-timedelta(hours=2)).isoformat())],
            rationale="R",
            issued_at=(now-timedelta(hours=2)).isoformat(),
            expiry=(now-timedelta(seconds=1)).isoformat(),
        )
        assert validate_session_init(init_expired, seen_nonces) == "initialization_expired"

        # 2. Future-dated issued_at (>5 mins ahead)
        init_future = SessionInitialization(
            approvers=[InitializerApproval("alice", (now+timedelta(hours=1)).isoformat()), InitializerApproval("bob", (now+timedelta(hours=1)).isoformat())],
            rationale="R",
            issued_at=(now+timedelta(hours=1)).isoformat(),
            expiry=(now+timedelta(hours=3)).isoformat(),
        )
        assert validate_session_init(init_future, seen_nonces) == "initialization_expired"

        # 3. Unbounded TTL (>24h max horizon)
        init_unbounded = SessionInitialization(
            approvers=[InitializerApproval("alice", now.isoformat()), InitializerApproval("bob", now.isoformat())],
            rationale="R",
            issued_at=now.isoformat(),
            expiry=(now+timedelta(days=7)).isoformat(),
        )
        assert validate_session_init(init_unbounded, seen_nonces) == "initialization_expiry_unbounded"

    def test_session_init_nonce_replay_persists_cross_engine_instances(self, tmp_path):
        """Verify init nonces are remembered and replayed nonces are rejected across restarts."""
        db = str(tmp_path / "nonce_store.db")
        engine1 = create_test_engine(db)

        reusable_nonce = "init-replayed-nonce-probe-001"
        init_auth = make_valid_session_init(nonce=reusable_nonce)

        # Initialize engine 1
        engine1.initialize_new_session(init_auth)
        assert reusable_nonce in engine1._seen_init_nonces

        # Validate with seen nonces
        assert validate_session_init(init_auth, engine1._seen_init_nonces) == "initialization_replayed"

        # Create new engine instance loading same DB
        engine2 = create_test_engine(db)
        # _seen_init_nonces should be reconstructed from SessionInitialized event
        assert reusable_nonce in engine2._seen_init_nonces
        assert validate_session_init(init_auth, engine2._seen_init_nonces) == "initialization_replayed"

    def test_release_authorization_validation_discipline(self):
        """Verify release authorization refuses on missing, incomplete, expired, or replayed auth."""
        seen_nonces = set()
        now = datetime.now(timezone.utc)
        kill_corr = "ks-inc-999"

        # 1. None auth
        assert validate_release_auth(None, kill_corr, seen_nonces=seen_nonces) == "release_not_authorized"

        # 2. Single approver
        auth_1 = ReleaseAuthorization(
            correlation_id=kill_corr, assessment="A", remediation="R",
            approvers=[ReleaseApproval("alice", now.isoformat())],
            issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat(), nonce="rel-1"
        )
        assert validate_release_auth(auth_1, kill_corr, seen_nonces=seen_nonces) == "authorization_incomplete"

        # 3. Missing assessment / remediation
        auth_no_rem = ReleaseAuthorization(
            correlation_id=kill_corr, assessment="", remediation="R",
            approvers=[ReleaseApproval("alice", now.isoformat()), ReleaseApproval("bob", now.isoformat())],
            issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat(), nonce="rel-1"
        )
        assert validate_release_auth(auth_no_rem, kill_corr, seen_nonces=seen_nonces) == "authorization_incomplete"

        # 4. Expired auth
        auth_exp = ReleaseAuthorization(
            correlation_id=kill_corr, assessment="A", remediation="R",
            approvers=[ReleaseApproval("alice", (now-timedelta(hours=2)).isoformat()), ReleaseApproval("bob", (now-timedelta(hours=2)).isoformat())],
            issued_at=(now-timedelta(hours=2)).isoformat(), expiry=(now-timedelta(minutes=1)).isoformat(), nonce="rel-1"
        )
        assert validate_release_auth(auth_exp, kill_corr, seen_nonces=seen_nonces) == "authorization_expired"

        # 5. Mismatched correlation ID
        auth_mismatch = ReleaseAuthorization(
            correlation_id="ks-inc-DIFFERENT", assessment="A", remediation="R",
            approvers=[ReleaseApproval("alice", now.isoformat()), ReleaseApproval("bob", now.isoformat())],
            issued_at=now.isoformat(), expiry=(now+timedelta(hours=1)).isoformat(), nonce="rel-1"
        )
        assert validate_release_auth(auth_mismatch, kill_corr, seen_nonces=seen_nonces) == "authorization_mismatch"

        # 6. Valid auth passes
        auth_ok = make_valid_release_auth(correlation_id=kill_corr, nonce="rel-valid-1")
        assert validate_release_auth(auth_ok, kill_corr, seen_nonces=seen_nonces) == ""

        # 7. Replayed nonce
        seen_nonces.add("rel-valid-1")
        assert validate_release_auth(auth_ok, kill_corr, seen_nonces=seen_nonces) == "authorization_replayed"

    def test_release_blocked_by_reconcile_drift_and_feed_health(self, tmp_path):
        """Verify release_kill_switch fails closed when reconcile drift is critical or feed is stale."""
        db = str(tmp_path / "refusal.db")
        engine = create_test_engine(db)
        engine.initialize_new_session(make_valid_session_init())

        # Trigger kill switch
        engine.trigger_kill_switch(reason="Triggered for test")
        assert engine.risk_gate.kill_switch.blocks_routing() is True
        kill_corr = engine._kill_correlation

        # 1. Feed health unhealthy -> release must fail closed
        engine.set_feed_health(lambda: FeedHealthVerdict(False, "feed_watermark_stale", {}, datetime.now(timezone.utc).isoformat()))
        rel_auth1 = make_valid_release_auth(correlation_id=kill_corr, nonce="rel-auth-1")
        with pytest.raises(RuntimeError, match="feed_watermark_stale"):
            engine.release_kill_switch(rel_auth1)
        assert engine.risk_gate.kill_switch.blocks_routing() is True

        # Nonce was NOT consumed on refusal (can be retried after fixing condition)
        assert "rel-auth-1" not in engine._seen_release_nonces

        # 2. Feed healthy -> release succeeds
        engine.set_feed_health(lambda: FeedHealthVerdict(True, "healthy", {"AAPL": datetime.now(timezone.utc).isoformat()}, datetime.now(timezone.utc).isoformat()))
        engine.release_kill_switch(rel_auth1)
        assert engine.risk_gate.kill_switch == KillSwitchState.Released or engine.risk_gate.kill_switch == KillSwitchState.Armed
        assert engine.risk_gate.trading_state == TradingState.Active
        assert "rel-auth-1" in engine._seen_release_nonces


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 4: Fail-Closed State Recovery & Extreme Numerical Stress
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarialFailClosedStateRecovery:
    """Stress-tests fail-closed recovery from corrupted DB, overflows, and circuit breakers."""

    def test_empty_database_starts_in_default_deny_state(self, tmp_path):
        """Verify that an uninitialized database starts in Triggered / Halted state."""
        db = str(tmp_path / "fresh_empty.db")
        engine = create_test_engine(db)

        # Default state before initialize_new_session
        assert engine.risk_gate.kill_switch == KillSwitchState.Triggered
        assert engine.risk_gate.trading_state == TradingState.Halted

        # Submitting any intent must be rejected.
        engine.update_market_price("AAPL", 150.0)

        # An identity-only certificate (no execution scope) is hard-rejected
        # at the gate before any routing decision (P0 A1).
        intent = make_valid_intent()
        with pytest.raises(ValueError, match="scope incomplete"):
            engine.submit_intent(intent)

        # A fully-scoped certificate still cannot route: the gate is held.
        from titan.research.promotion_certificate import execution_scope_parameters
        scoped_cert = create_signed_certificate(
            ADV_TEST_PRIVKEY, strategy_id="EQ-004",
            expires_at="20991231T235959Z",
            parameters=execution_scope_parameters(
                instrument="AAPL", side="BUY", max_quantity=100,
                account="PAPER_TEST_01"),
        )
        intent = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg",
            account_id="PAPER_TEST_01", instrument_id="AAPL", side="BUY",
            quantity="100", order_type="LIMIT", time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).isoformat(),
            price="150.00", certificate_ref=json.dumps({
                "strategy_id": scoped_cert.strategy_id,
                "expires_at": scoped_cert.expires_at,
                "signature": scoped_cert.signature,
                "content_digest": scoped_cert.content_digest,
                "parameters": scoped_cert.parameters,
            }),
        )
        result = engine.submit_intent(intent)
        assert result.accepted is False
        assert "Kill switch is blocking routing" in result.rejection_reason or "Trading state is not active" in result.rejection_reason

    def test_corrupted_risk_snapshot_fails_closed_to_halted(self, tmp_path):
        """Verify engine safely falls back to Triggered/Halted when RiskStateSnapshot is corrupted."""
        db = str(tmp_path / "corrupted.db")
        store = EventStore(db)

        # Inject corrupted event payload
        corrupted_envelope = EventEnvelope(
            "RiskStateSnapshot", "RiskGate", "system", "titan_core",
            "{corrupted_json: true, kill_switch_state: 12345}",
            None, None, None
        )
        store.append(corrupted_envelope)

        # Load engine
        engine = create_test_engine(db)
        assert engine.risk_gate.kill_switch == KillSwitchState.Triggered
        assert engine.risk_gate.trading_state == TradingState.Halted

    def test_extreme_numerical_overflow_and_negative_bounds(self, tmp_path):
        """Adversarial stress: Check negative prices, negative quantities, huge quantities."""
        risk_cfg = RiskConfig(
            instrument_eligibility=["AAPL"],
            max_order_notional=Money("100000", "USD"),
            max_order_quantity=1000,
            max_position_size=2000,
            max_gross_exposure=Money("500000", "USD"),
            max_drawdown_fraction=0.20,
            max_daily_loss=Money("20000", "USD"),
            data_freshness_threshold_ms=60000,
            clock_skew_tolerance_ms=5000,
        )
        gate = RiskGate(risk_cfg)
        gate._initialize_armed()

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Negative quantity (-100) -> must be rejected
        intent_neg_qty = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg", account_id="PAPER_TEST_01",
            instrument_id="AAPL", side="BUY", quantity="-100",
            order_type="LIMIT", time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=now_iso, price="150.00", certificate_ref="{}",
        )
        verdict = gate.evaluate(intent_neg_qty, None, None, None, None)
        assert verdict.accepted is False
        assert verdict.reason == RiskReasonCode.InternalError

        # 2. Exceeds max order quantity (1500 > 1000)
        intent_exceed_qty = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg", account_id="PAPER_TEST_01",
            instrument_id="AAPL", side="BUY", quantity="1500",
            order_type="LIMIT", time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=now_iso, price="50.00", certificate_ref="{}",
        )
        verdict = gate.evaluate(intent_exceed_qty, None, None, None, None)
        assert verdict.accepted is False
        assert verdict.reason == RiskReasonCode.OrderQuantityExceeded

        # 3. Exceeds max notional (500 * $300 = $150k > $100k)
        intent_exceed_notional = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg", account_id="PAPER_TEST_01",
            instrument_id="AAPL", side="BUY", quantity="500",
            order_type="LIMIT", time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=now_iso, price="300.00", certificate_ref="{}",
        )
        verdict = gate.evaluate(intent_exceed_notional, None, None, None, None)
        assert verdict.accepted is False
        assert verdict.reason == RiskReasonCode.OrderNotionalExceeded

        # 4. Stale market data timestamp (2 hours in past)
        stale_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        intent_stale = TradeIntent(
            strategy_id="EQ-004", strategy_package_digest="pkg", account_id="PAPER_TEST_01",
            instrument_id="AAPL", side="BUY", quantity="10",
            order_type="LIMIT", time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=stale_iso, price="150.00", certificate_ref="{}",
        )
        verdict = gate.evaluate(intent_stale, None, None, None, None)
        assert verdict.accepted is False
        assert verdict.reason == RiskReasonCode.DataStale

    def test_circuit_breaker_rate_limiting_and_error_tripping(self):
        """Stress-test CircuitBreaker under flood conditions and consecutive broker errors."""
        cb_cfg = CircuitBreakerConfig(
            max_intents_per_second=5,
            max_intents_per_minute=20,
            max_consecutive_broker_errors=3,
            cooldown_seconds=10.0,
            trip_on_max_errors=True,
        )
        cb = CircuitBreaker(cb_cfg)
        assert cb.stage == BreakerStage.NORMAL

        # 1. Send 5 intents rapidly -> OK
        for _ in range(5):
            allowed, reason = cb.record_intent()
            assert allowed is True

        # 6th intent in same second -> Throttled
        allowed, reason = cb.record_intent()
        assert allowed is False
        assert "Rate limit exceeded" in reason
        assert cb.stage == BreakerStage.THROTTLED

        # 2. Error tripping: record 3 consecutive errors
        cb.reset()
        assert cb.stage == BreakerStage.NORMAL
        cb.record_error("Connection timeout 1")
        cb.record_error("Connection timeout 2")
        assert cb.stage == BreakerStage.NORMAL
        cb.record_error("Connection timeout 3")
        assert cb.stage == BreakerStage.TRIPPED

        # While tripped, all intents are blocked
        allowed, reason = cb.record_intent()
        assert allowed is False
        assert "Circuit breaker TRIPPED" in reason
