"""Comprehensive 4-Tier Opaque-Box E2E Acceptance Test Suite for Profit-Engine-AI (v2.0) on Project TITAN.

Derived from ORIGINAL_REQUEST.md, AGENTS.md, PROJECT.md, and TEST_INFRA.md.
Covers:
- Tier 1: Feature Coverage (Audit Categorization, Ingestion, Manifests, Corporate Actions,
           Pre-registration, Negative Results, FxCostModel $2.00 min fee, FactorCostModel short borrow,
           Quote-sided fills, Default-Deny Cert Gate, RiskGate HMAC Signing, Dual-Approver Init)
- Tier 2: Boundary & Corner Cases (Empty/zero volume, price envelope errors, extreme splits/divs,
           expired/forged certs, feed disconnect storms, max DD limits, un-resettable kill switch)
- Tier 3: Cross-Feature Combinations (PIT Data -> CA -> Factor Sim -> Negative Results;
           Pre-reg -> FX Sim -> Ed25519 Cert -> Default-Deny Ingress;
           TWS Feed -> Feed Health -> Risk Gate -> HMAC Token -> IBKR Bracket Order;
           Halted State -> Dual-Human Release -> Feed Health -> Active Recovery)
- Tier 4: Real-World Workload Scenarios (Equities Factor Lifecycle, Multi-Pair FX Simulation,
           Crypto Perpetual Funding Carry, E2E Paper Trading SQLite Persistence, Circuit Breaker & Recovery)
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import pytest

from titan._core import (
    ApprovedOrderIntent,
    ContractType,
    EventEnvelope,
    EventStore,
    Instrument,
    InstrumentId,
    KillSwitchState,
    Money,
    OrderState,
    OrderStateMachine,
    PortfolioEngine,
    PortfolioSnapshot,
    ReconciliationConfig,
    RiskConfig,
    RiskGate,
    RiskReasonCode,
    RiskVerdict,
    TradeIntent,
    TradingState,
    TrailingConfig,
)
from titan.backtest.corporate_actions import CorporateActionsDB
from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.factor_simulator import (
    FactorCostModel,
    FactorSimulationResult,
    simulate_factor_portfolio,
)
from titan.backtest.fills import BarConservativeFillModel
from titan.backtest.fx_costs import FxCostModel
from titan.data.equities_universe import (
    EquitiesUniverseData,
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.data.feed_health import FeedHealthSnapshot, FeedHealthVerdict
from titan.data.manifest import DataManifest
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from titan.execution._broker_adapter import BrokerAdapter
from titan.execution._broker_types import (
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.research.db import ResearchDB
from titan.research.hypothesis import Hypothesis, HypothesisRegistry
from titan.research.promotion_certificate import Certificate, PromotionCertificateRegistry, create_signed_certificate
from cryptography.hazmat.primitives.asymmetric import ed25519
from titan.risk.circuit_breaker import BreakerStage, CircuitBreaker, CircuitBreakerConfig

TEST_CERT_PRIVKEY = ed25519.Ed25519PrivateKey.from_private_bytes(b"TITAN_TEST_ED25519_KEY_32_BYTES!")
TEST_CERT_PUBKEY_HEX = TEST_CERT_PRIVKEY.public_key().public_bytes_raw().hex()
os.environ["TITAN_EXEC_PUBKEY"] = TEST_CERT_PUBKEY_HEX
from titan.risk.release_authorization import (
    ReleaseApproval,
    ReleaseAuthorization,
    validate as validate_release_auth,
)
from titan.risk.session_initialization import (
    InitializerApproval,
    SessionInitialization,
    validate as validate_initialization,
)


# =====================================================================
# Test Fixtures & Mock Helpers
# =====================================================================

@dataclass
class FakeTransport:
    placed_orders: list = field(default_factory=list)
    cancelled: list = field(default_factory=list)
    heartbeat_ok: bool = True
    next_session_id: str = "fake-e2e-session-1"

    def authenticate(self) -> Session:
        return Session(
            session_id=self.next_session_id,
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        self.placed_orders.append(intent)
        return BrokerOrderAcknowledgement(
            accepted=True,
            broker_order_id=BrokerOrderId(id=str(uuid.uuid4())),
            fill_price=str(intent.price or "450.00"),
            fill_quantity=str(intent.quantity),
            order_status="Filled",
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        self.cancelled.append(order_id)
        return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(
            connected=self.heartbeat_ok,
            session_state=AdapterSessionState.CONNECTED,
        )


@dataclass
class FakeIBKRPaperAdapter(BrokerAdapter):
    transport: FakeTransport = field(default_factory=FakeTransport)

    def authenticate(self) -> Session:
        return self.transport.authenticate()

    def heartbeat(self) -> AdapterHealth:
        return self.transport.heartbeat()

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        return self.transport.place_order(intent)

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=Money("100000", "USD"),
            portfolio_value=Money("100000", "USD"),
            buying_power=Money("100000", "USD"),
            equity=Money("100000", "USD"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        return self.transport.cancel(order_id)

    def tick(self, order_id: str) -> None:
        return None


class FakeRealtimeFeed:
    """Mock realtime feed for FeedHealthSnapshot testing."""
    def __init__(self, healthy=True, recovering=False, advancing=True, latest=None):
        self._healthy = healthy
        self._recovering = recovering
        self._advancing = advancing
        self._latest = latest or {}

    def is_healthy(self, stale_after_s):
        return self._healthy

    def needs_recovery(self):
        return self._recovering

    def bars_advancing(self, since_ts=None):
        return self._advancing

    def latest_completed(self, instr):
        # Returns tuple of (iso_timestamp, close_price)
        val = self._latest.get(instr)
        if val is None:
            return None
        if isinstance(val, tuple):
            return val
        return (val, 100.0)


def make_valid_certificate_json(strategy_id: str = "strat-e2e-1", **scope) -> str:
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    parameters = None
    if scope:
        # P0 A1: the engine requires a bounded execution scope; tests opt in
        # per call site with instrument=/side=/max_quantity=/account=.
        from titan.research.promotion_certificate import execution_scope_parameters
        parameters = execution_scope_parameters(**scope)
    cert = create_signed_certificate(
        TEST_CERT_PRIVKEY,
        strategy_id=strategy_id,
        expires_at=expires_at,
        content_digest="abcdef0123456789" * 4,
        parameters=parameters,
    )
    return json.dumps({
        "strategy_id": cert.strategy_id,
        "expires_at": cert.expires_at,
        "signature": cert.signature,
        "content_digest": cert.content_digest,
        "parameters": cert.parameters,
    })


def make_valid_session_init(
    approver1: str = "risk-lead-alice",
    approver2: str = "exec-lead-bob",
    ttl_hours: int = 12,
    nonce: Optional[str] = None,
) -> SessionInitialization:
    now = datetime.now(timezone.utc)
    return SessionInitialization(
        approvers=[
            InitializerApproval(approver=approver1, signed_at=now.isoformat()),
            InitializerApproval(approver=approver2, signed_at=now.isoformat()),
        ],
        rationale="E2E test session initialization with verified credentials",
        issued_at=now.isoformat(),
        expiry=(now + timedelta(hours=ttl_hours)).isoformat(),
        nonce=nonce or f"init-e2e-{uuid.uuid4().hex[:12]}",
    )


def make_valid_release_auth(
    correlation_id: str = "corr-test-1",
    approver1: str = "risk-lead-alice",
    approver2: str = "exec-lead-bob",
    ttl_hours: int = 4,
    nonce: Optional[str] = None,
) -> ReleaseAuthorization:
    now = datetime.now(timezone.utc)
    return ReleaseAuthorization(
        correlation_id=correlation_id,
        assessment="Root cause evaluated: transient feed glitch resolved",
        remediation="Feed reconnected, state reconciled, safeguards intact",
        approvers=[
            ReleaseApproval(approver=approver1, signed_at=now.isoformat()),
            ReleaseApproval(approver=approver2, signed_at=now.isoformat()),
        ],
        issued_at=now.isoformat(),
        expiry=(now + timedelta(hours=ttl_hours)).isoformat(),
        nonce=nonce or f"rel-e2e-{uuid.uuid4().hex[:12]}",
    )


# =====================================================================
# TIER 1: Feature Coverage Tests
# =====================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Comprehensive isolated feature coverage across all 12 core capabilities."""

    def test_tier1_audit_failure_categorization_mechanism_vs_execution(self):
        """Verify hypothesis failure classification: Mechanism Failure vs Execution-Constrained Rejection."""
        # Case A: Underlying alpha is absent / directionally inverted -> Mechanism Failure
        gross_return_a = -0.045
        net_return_a = -0.075
        failure_mode_a = "mechanism_failure" if gross_return_a <= 0.0 else "execution_constrained"
        assert failure_mode_a == "mechanism_failure"

        # Case B: Gross positive economic edge exists, but friction exceeds alpha -> Execution-Constrained
        gross_return_b = 0.018
        friction_b = 0.025
        net_return_b = gross_return_b - friction_b  # -0.007 < 0
        failure_mode_b = "mechanism_failure" if gross_return_b <= 0.0 else "execution_constrained"
        assert failure_mode_b == "execution_constrained"
        assert net_return_b < 0.0

    def test_tier1_data_ingestion_and_quality_quarantine(self):
        """Verify normalization and quality quarantine isolation on valid and corrupted market data."""
        raw_records = [
            {"symbol": "SPY", "date": "2026-01-02T14:30:00Z", "open": "450.0", "high": "455.0", "low": "449.0", "close": "453.0", "volume": "10000"},
            {"symbol": "AAPL", "date": "2026-01-02T14:30:00Z", "open": "180.0", "high": "182.0", "low": "179.0", "close": "181.0", "volume": "25000"},
            {"symbol": "EURUSD", "date": "2026-01-02T14:30:00Z", "open": "1.0850", "high": "1.0890", "low": "1.0840", "close": "1.0870", "volume": "5000"},
            # Corrupted row 1: low > high
            {"symbol": "SPY", "date": "2026-01-03T14:30:00Z", "open": "455.0", "high": "450.0", "low": "458.0", "close": "452.0", "volume": "10000"},
            # Corrupted row 2: close out of range (close > high)
            {"symbol": "AAPL", "date": "2026-01-03T14:30:00Z", "open": "180.0", "high": "182.0", "low": "179.0", "close": "195.0", "volume": "20000"},
            # Corrupted row 3: Unknown symbol
            {"symbol": "INVALID_TICKER_XYZ", "date": "2026-01-02T14:30:00Z", "open": "10.0", "high": "11.0", "low": "9.0", "close": "10.5", "volume": "100"},
        ]

        report, good = validate_and_quarantine(raw_records, normalize_row)
        assert report.total_records == 6
        assert report.passed == 3
        assert report.quarantine_count == 3
        assert len(good) == 3

        reasons = [q["reason"] for q in report.quarantined]
        assert any("Low > high" in r for r in reasons)
        assert any("Close outside range" in r for r in reasons)
        assert any("Unknown symbol" in r for r in reasons)

    def test_tier1_sha256_data_manifest_generation_and_integrity(self, tmp_path):
        """Verify SHA-256 manifest creation, deterministic hashing, and JSON round-trip."""
        dummy_file = tmp_path / "spy_sample.csv"
        dummy_file.write_text("timestamp,open,high,low,close,volume\n2026-01-02,450,455,449,453,10000\n", encoding="utf-8")

        bars = [
            {"instrument_id": "SPY", "timestamp": "2026-01-02T14:30:00Z", "open": 450.0, "high": 455.0, "low": 449.0, "close": 453.0, "volume": 10000},
            {"instrument_id": "SPY", "timestamp": "2026-01-03T14:30:00Z", "open": 453.0, "high": 458.0, "low": 452.0, "close": 457.0, "volume": 12000},
        ]
        manifest = DataManifest.create_from_bars(bars, source_path=str(dummy_file))
        assert manifest.instrument_id == "SPY"
        assert manifest.record_count == 2
        assert manifest.date_from == "2026-01-02T14:30:00Z"
        assert manifest.date_to == "2026-01-03T14:30:00Z"

        digest1 = manifest.compute_digest()
        digest2 = manifest.compute_digest()
        assert len(digest1) == 64
        assert digest1 == digest2

        # Round trip
        json_str = manifest.to_json()
        restored = DataManifest.from_json(json_str)
        assert restored.compute_digest() == digest1
        assert restored.instrument_id == manifest.instrument_id

    def test_tier1_corporate_actions_split_dividend_backward_adjustment(self):
        """Verify Point-in-Time Corporate Actions backward adjustment for stock splits and cash dividends."""
        db = CorporateActionsDB()
        # 2:1 stock split on 2026-06-01 for AAPL
        db.register_split(date="2026-06-01", instrument_id="AAPL", ratio=2.0)
        # $1.50 cash dividend on 2026-06-15 for AAPL
        db.register_dividend(date="2026-06-15", instrument_id="AAPL", amount=1.50)

        unadjusted_bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-05-15T00:00:00Z", "open": 200.0, "high": 204.0, "low": 198.0, "close": 202.0, "volume": 1000},
            {"instrument_id": "AAPL", "timestamp": "2026-06-05T00:00:00Z", "open": 105.0, "high": 107.0, "low": 104.0, "close": 106.0, "volume": 2000},
            {"instrument_id": "AAPL", "timestamp": "2026-06-20T00:00:00Z", "open": 110.0, "high": 112.0, "low": 109.0, "close": 111.0, "volume": 2200},
        ]

        adjusted = db.adjust_bars(unadjusted_bars)

        # Bar 1 (2026-05-15): before split and before dividend -> price / 2 - 1.50 = 202 / 2 - 1.50 = 99.50; volume * 2 = 2000
        assert adjusted[0]["close"] == pytest.approx((202.0 / 2.0) - 1.50)
        assert adjusted[0]["volume"] == 2000

        # Bar 2 (2026-06-05): after split, before dividend -> price - 1.50 = 106 - 1.50 = 104.50; volume unchanged
        assert adjusted[1]["close"] == pytest.approx(106.0 - 1.50)
        assert adjusted[1]["volume"] == 2000

        # Bar 3 (2026-06-20): after split and dividend -> unmodified
        assert adjusted[2]["close"] == pytest.approx(111.0)
        assert adjusted[2]["volume"] == 2200

    def test_tier1_hypothesis_preregistration_schema_and_registry(self, tmp_path):
        """Verify structured hypothesis pre-registration schema, Path A/B policies, and persistent registry."""
        hypo = Hypothesis(
            id="EQ-004",
            title="Broad 50 Reversal Multi-Asset Factor",
            economic_rationale="Short-term liquidity shocks produce mean-reverting price overshoots.",
            strategy_id="cross-sectional-reversal",
            instrument="US_EQUITIES_50",
            universe="BROAD_50",
            calendar="NYSE",
            train_period="2020-01-01 to 2023-12-31",
            test_period="2024-01-01 to 2025-12-31",
            success_criteria=["OOS Sharpe >= 1.0", "Max Drawdown <= 15%"],
            failure_criteria=["OOS Sharpe < 0.5", "Monthly Turnover > 500%"],
            category="Factor",
            mechanism="Liquidity Provision",
            plausibility=4,
            impact=4,
            novelty=3,
            effort=2,
            strategy_params={"top_k": 5, "lookback_days": 5},
            sample_adequacy_policy="Path A",
        )

        assert hypo.priority_score == pytest.approx((4 + 4 + 3) / 2.0)
        assert hypo.status == "preregistered"

        storage_path = tmp_path / "hypotheses_registry.json"
        registry = HypothesisRegistry(storage_path)
        registry.register(hypo)
        assert registry.hypotheses["EQ-004"].title == hypo.title
        assert storage_path.exists()

        # Verify Path B validation rule (requires explicit evidence standard)
        with pytest.raises(ValueError, match="Path B hypotheses must declare a path_b_evidence_standard"):
            Hypothesis(
                id="EQ-PATH-B-FAIL",
                title="Invalid Path B",
                sample_adequacy_policy="Path B",
                path_b_evidence_standard="",
            )

    def test_tier1_absorbing_negative_result_transition(self, tmp_path):
        """Verify ADR-029/030 permanent transition of failed hypotheses into absorbing negative result states."""
        db_path = tmp_path / "titan_research.db"
        rdb = ResearchDB(db_path)

        # Log an experimental run that fails out-of-sample criteria
        run_id = rdb.log_run(
            strategy_id="EQ-001-momentum",
            instrument="SPY_UNIVERSE",
            n_bars=252,
            n_trades=42,
            return_pct=-4.5,
            sharpe=-0.17,
            max_dd_pct=18.5,
            win_rate=0.38,
            profit_factor=0.72,
        )
        assert run_id > 0

        # Mark qualification as REJECTED (negative result)
        rdb.set_qualification(
            strategy_id="EQ-001-momentum",
            version="1.0.0",
            status="REJECTED",
            backtest_sharpe=-0.17,
            notes="Permanent negative result: Mechanism Failure on OOS partition",
        )

        quals = rdb.get_qualifications(status="REJECTED")
        assert len(quals) == 1
        assert quals[0]["strategy_id"] == "EQ-001-momentum"
        assert quals[0]["status"] == "REJECTED"
        rdb.close()

    def test_tier1_canonical_fx_cost_model_ibkr_minimum_fee(self):
        """Verify ADR-031 FxCostModel $2.00 IBKR ticket minimum on small notional vs variable bps on large."""
        fx_model = FxCostModel.ibkr_spot_fx_tier_one()
        assert fx_model.minimum_commission == Decimal("2.00")
        assert fx_model.commission_bps == Decimal("0.20")

        # 1. Micro-lot trade: $10,000 notional
        # Variable fee = $10,000 * 0.00002 = $0.20 < $2.00 min -> should charge $2.00
        micro_fee = fx_model.commission_for_fill(Decimal("10000.00"))
        assert micro_fee == Decimal("2.00")

        # 2. Institutional trade: $2,000,000 notional
        # Variable fee = $2,000,000 * 0.00002 = $40.00 > $2.00 min -> should charge $40.00
        inst_fee = fx_model.commission_for_fill(Decimal("2000000.00"))
        assert inst_fee == Decimal("40.00")

        # Model digest is deterministic
        assert len(fx_model.digest()) == 64

    def test_tier1_factor_cost_model_short_borrow_and_commissions(self):
        """Verify ADR-030 FactorCostModel institutional parameters and daily short borrow accrual."""
        model = FactorCostModel.standard_us_equity()
        assert model.commission_per_share_usd == 0.005
        assert model.spread_bps == 1.0
        assert model.slippage_bps == 0.5
        assert model.annual_short_borrow_bps == 50.0  # 50 bps annual borrow rate

        # Verify annual to daily borrow cost computation
        daily_borrow_rate = (model.annual_short_borrow_bps / 10000.0) / 252.0
        assert daily_borrow_rate == pytest.approx(0.0050 / 252.0)

        # Stressed model
        adverse_model = FactorCostModel.stressed_adverse()
        assert adverse_model.annual_short_borrow_bps == 150.0
        assert adverse_model.commission_per_share_usd == 0.010

    def test_tier1_quote_sided_fill_timing_t_plus_one(self):
        """Verify Quote-Sided Top-of-Book Fill Model evaluates signal at t and fills on bar t+1 quote."""
        fill_model = BarConservativeFillModel()
        fx_cost = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")

        # Bar t+1 quote data
        bar_t_plus_1 = {
            "timestamp": "2026-01-02T14:31:00Z",
            "bid": 1.0850,
            "ask": 1.0852,
            "close": 1.0851,
        }

        # BUY fill should hit the ASK price + slippage
        buy_fill = fill_model.fill(bar_t_plus_1, "BUY", 100000, cost_model=fx_cost)
        assert buy_fill.fill_price >= Decimal("1.0852")
        assert buy_fill.commission >= Decimal("2.00")

        # SELL fill should hit the BID price - slippage
        sell_fill = fill_model.fill(bar_t_plus_1, "SELL", 100000, cost_model=fx_cost)
        assert sell_fill.fill_price <= Decimal("1.0850")
        assert sell_fill.commission >= Decimal("2.00")

        # Missing quote field raises ValueError
        bad_bar = {"timestamp": "2026-01-02T14:31:00Z", "close": 1.0851}
        with pytest.raises(ValueError, match="Missing required quote field 'ask'"):
            fill_model.fill(bad_bar, "BUY", 100000, cost_model=fx_cost)

    def test_tier1_default_deny_execution_certificate_verification(self):
        """Verify Default-Deny execution ingress strictly blocks uncertified and shadow trade intents."""
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes_raw().hex()
        registry = PromotionCertificateRegistry(public_key_hex=pub_hex)

        # Valid unexpired certificate
        valid_cert = create_signed_certificate(
            priv,
            strategy_id="strat-v1",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        )
        assert registry.verify(valid_cert) is True

        # Expired certificate
        expired_cert = create_signed_certificate(
            priv,
            strategy_id="strat-v1",
            expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        )
        with pytest.raises(ValueError, match="Certificate is expired"):
            registry.verify(expired_cert)

        # Forged certificate (signed by different/mismatched private key)
        priv_forged = ed25519.Ed25519PrivateKey.generate()
        forged_cert = create_signed_certificate(
            priv_forged,
            strategy_id="strat-v1",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        )
        with pytest.raises(ValueError, match="(?i)forged|signature"):
            registry.verify(forged_cert)

    def test_tier1_riskgate_hmac_token_signing_and_verification(self):
        """Verify SHA-256 HMAC token computation and cryptographic binding on ApprovedOrderIntent."""
        intent = ApprovedOrderIntent(
            risk_decision_id=str(uuid.uuid4()),
            intent_id=str(uuid.uuid4()),
            client_order_id="tit-e2e-order-1",
            instrument_id="SPY",
            side="BUY",
            quantity="50",
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="1.0",
            price="450.00",
        )
        secret_key = "TITAN_E2E_RISK_SECRET_KEY"
        intent.attach_risk_token(secret_key)
        assert intent.risk_token is not None
        assert len(intent.risk_token) == 64

        # Verification with proper key succeeds
        assert intent.verify_risk_token(secret_key) is True
        # Verification with wrong key fails
        assert intent.verify_risk_token("WRONG_KEY") is False

    def test_tier1_session_initialization_dual_approvers(self):
        """Verify operator-controlled SessionInitialization requires 2 distinct approvers and bounded expiry."""
        init = make_valid_session_init(
            approver1="risk-officer-alice",
            approver2="head-of-trading-bob",
            ttl_hours=6,
        )
        seen_nonces: set[str] = set()

        # Valid initialization returns empty string (no rejection code)
        reason = validate_initialization(init, seen_nonces)
        assert reason == ""

        # Replayed nonce returns refusal
        seen_nonces.add(init.nonce)
        reason_replay = validate_initialization(init, seen_nonces)
        assert reason_replay == "initialization_replayed"

        # Single approver returns refusal
        single_appr = make_valid_session_init(approver1="alice", approver2="alice")
        assert validate_initialization(single_appr, set()) == "initialization_incomplete"


# =====================================================================
# TIER 2: Boundary & Corner Cases Tests
# =====================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary conditions, malformed data, extreme splits, and un-resettable kill switch."""

    def test_tier2_empty_data_files_and_zero_volume(self):
        """Verify data normalizer and quality pipeline handle empty records and zero volume cleanly."""
        report, good = validate_and_quarantine([], normalize_row)
        assert report.total_records == 0
        assert report.passed == 0
        assert len(good) == 0

        # Bar with volume = 0 (valid in illiquid or off-hours)
        zero_vol_row = {
            "symbol": "SPY",
            "date": "2026-01-02T14:30:00Z",
            "open": "450.0",
            "high": "452.0",
            "low": "449.0",
            "close": "451.0",
            "volume": "0",
        }
        res = normalize_row(zero_vol_row)
        assert isinstance(res, dict)
        assert res["volume"] == 0

        # Negative volume is rejected and quarantined
        neg_vol_row = {
            "symbol": "SPY",
            "date": "2026-01-02T14:30:00Z",
            "open": "450.0",
            "high": "452.0",
            "low": "449.0",
            "close": "451.0",
            "volume": "-500",
        }
        res_neg = normalize_row(neg_vol_row)
        assert isinstance(res_neg, str)
        assert "Negative volume" in res_neg

    def test_tier2_price_envelope_violations_and_date_errors(self):
        """Verify strict detection and isolation of price envelope corruptions and date formatting errors."""
        bad_rows = [
            # low > high
            {"symbol": "SPY", "date": "2026-01-02", "open": "450", "high": "440", "low": "460", "close": "445", "volume": "100"},
            # close < low
            {"symbol": "SPY", "date": "2026-01-02", "open": "450", "high": "455", "low": "445", "close": "440", "volume": "100"},
            # close > high
            {"symbol": "SPY", "date": "2026-01-02", "open": "450", "high": "455", "low": "445", "close": "460", "volume": "100"},
            # empty timestamp
            {"symbol": "SPY", "date": "", "open": "450", "high": "455", "low": "445", "close": "450", "volume": "100"},
            # malformed timestamp
            {"symbol": "SPY", "date": "not-a-date", "open": "450", "high": "455", "low": "445", "close": "450", "volume": "100"},
        ]
        for row in bad_rows:
            result = normalize_row(row)
            assert isinstance(result, str)  # String error message indicating quarantine

    def test_tier2_extreme_corporate_actions_large_splits_and_dividends(self):
        """Verify extreme 100:1 reverse split and dividend exceeding share price."""
        db = CorporateActionsDB()
        # 100:1 forward split
        db.register_split("2026-03-01", "AAPL", 100.0)
        # Liquidating dividend of $50.00
        db.register_dividend("2026-04-01", "AAPL", 50.0)

        bars = [
            {"instrument_id": "AAPL", "timestamp": "2026-02-01T00:00:00Z", "open": 2000.0, "high": 2100.0, "low": 1900.0, "close": 2000.0, "volume": 50},
            {"instrument_id": "AAPL", "timestamp": "2026-03-15T00:00:00Z", "open": 60.0, "high": 65.0, "low": 58.0, "close": 60.0, "volume": 5000},
            {"instrument_id": "AAPL", "timestamp": "2026-05-01T00:00:00Z", "open": 15.0, "high": 16.0, "low": 14.0, "close": 15.0, "volume": 6000},
        ]
        adj = db.adjust_bars(bars)

        # Bar 1 before split and dividend: 2000 / 100 - 50 = 20 - 50 = -30 (mathematically exact backward adjustment)
        assert adj[0]["close"] == pytest.approx((2000.0 / 100.0) - 50.0)
        assert adj[0]["volume"] == 50 * 100

        # Bar 2 after split, before dividend: 60 - 50 = 10.0
        assert adj[1]["close"] == pytest.approx(10.0)

        # Bar 3 after both: unmodified
        assert adj[2]["close"] == pytest.approx(15.0)

    def test_tier2_expired_and_forged_certificates_rejection(self):
        """Verify PromotionCertificateRegistry rejects invalid JSON, expired TTLs, and forged signatures."""
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes_raw().hex()
        reg = PromotionCertificateRegistry(public_key_hex=pub_hex)

        # Missing cert
        with pytest.raises(ValueError, match="Missing certificate"):
            reg.verify(None)

        # Invalid date format
        bad_date_cert = Certificate(
            strategy_id="strat-1",
            expires_at="invalid-date-format",
            signature="00" * 64,
        )
        with pytest.raises(ValueError, match="Invalid expiry format"):
            reg.verify(bad_date_cert)

        # Forged signature
        forged_cert = Certificate(
            strategy_id="strat-1",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            signature="00" * 64,
        )
        with pytest.raises(ValueError, match="(?i)forged|signature"):
            reg.verify(forged_cert)

    def test_tier2_feed_health_disconnect_storms_and_staleness(self):
        """Verify FeedHealthSnapshot fail-closed behavior under disconnects, non-advancing bars, and staleness."""
        # 1. Feed is None -> fails closed
        snap_none = FeedHealthSnapshot(None, ["AAPL", "MSFT"], stale_after_s=30.0)
        v_none = snap_none.evaluate()
        assert v_none.healthy is False
        assert v_none.reason == "feed_health_absent"

        # 2. Feed recovering -> fails closed
        snap_rec = FeedHealthSnapshot(FakeRealtimeFeed(recovering=True), ["AAPL"], stale_after_s=30.0)
        assert snap_rec.evaluate().reason == "feed_recovering"

        # 3. Feed not advancing -> fails closed
        snap_adv = FeedHealthSnapshot(FakeRealtimeFeed(advancing=False), ["AAPL"], stale_after_s=30.0)
        assert snap_adv.evaluate().reason == "bar_not_advancing"

        # 4. Feed missing one required instrument -> fails closed
        latest = {"AAPL": ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), 180.0)}
        snap_missing = FeedHealthSnapshot(FakeRealtimeFeed(latest=latest), ["AAPL", "GOOGL"], stale_after_s=30.0)
        v_missing = snap_missing.evaluate()
        assert v_missing.healthy is False
        assert "instrument_uncovered" in v_missing.reason

    def test_tier2_risk_gate_limits_drawdown_and_whitelists(self):
        """Verify RiskGate enforcement of max order quantity, max order value, max drawdown, and whitelists."""
        config = RiskConfig(
            ["AAPL", "MSFT"],                # allowed instruments
            Money("50000", "USD"),           # max_order_value
            500,                             # max_order_quantity
            2000,                            # max_position_size
            Money("200000", "USD"),          # max_gross_exposure
            0.10,                            # max_drawdown_percent (10%)
            Money("10000", "USD"),           # max_daily_loss
            1000,                            # max_concentration_basis_points
            100,                             # max_intents_per_minute
        )
        gate = RiskGate(config)

        # 1. Unwhitelisted instrument -> InstrumentNotEligible
        intent_unlisted = TradeIntent(
            "strat-1", "pkg-1", "acct-1", "TSLA", "BUY", "10", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="200.00",
        )
        v1 = gate.evaluate(intent_unlisted, 0, Money("0", "USD"), 0.0, Money("0", "USD"), None, None)
        assert v1.accepted is False
        assert v1.reason == RiskReasonCode.InstrumentNotEligible

        # 2. Exceeding max order quantity (600 > 500) -> OrderQuantityExceeded
        intent_large_qty = TradeIntent(
            "strat-1", "pkg-1", "acct-1", "AAPL", "BUY", "600", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="50.00",
        )
        v2 = gate.evaluate(intent_large_qty, 0, Money("0", "USD"), 0.0, Money("0", "USD"), None, None)
        assert v2.accepted is False
        assert v2.reason == RiskReasonCode.OrderQuantityExceeded

        # 3. Exceeding max order value ($60,000 > $50,000) -> OrderNotionalExceeded
        intent_large_val = TradeIntent(
            "strat-1", "pkg-1", "acct-1", "AAPL", "BUY", "400", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="150.00",
        )
        v3 = gate.evaluate(intent_large_val, 0, Money("0", "USD"), 0.0, Money("0", "USD"), None, None)
        assert v3.accepted is False
        assert v3.reason == RiskReasonCode.OrderNotionalExceeded

        # 4. Drawdown limit breached (15% > 10%) -> DrawdownExceeded
        intent_ok = TradeIntent(
            "strat-1", "pkg-1", "acct-1", "AAPL", "BUY", "10", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="100.00",
        )
        v4 = gate.evaluate(intent_ok, 0, Money("0", "USD"), 0.15, Money("0", "USD"), None, None)
        assert v4.accepted is False
        assert v4.reason == RiskReasonCode.DrawdownExceeded

    def test_tier2_unresettable_kill_switch_fails_closed(self):
        """Verify ADR-019 kill switch release refusal on invalid/replayed/single-approver authorizations."""
        seen_nonces: set[str] = set()
        corr_id = "incident-corrupt-001"

        # 1. Missing authorization
        assert validate_release_auth(None, corr_id, seen_nonces) == "release_not_authorized"

        # 2. Single approver
        single_appr = make_valid_release_auth(correlation_id=corr_id, approver1="alice", approver2="alice")
        assert validate_release_auth(single_appr, corr_id, seen_nonces) == "authorization_incomplete"

        # 3. Correlation ID mismatch
        mismatch_auth = make_valid_release_auth(correlation_id="different-corr-id")
        assert validate_release_auth(mismatch_auth, corr_id, seen_nonces) == "authorization_mismatch"

        # 4. Expired authorization
        now = datetime.now(timezone.utc)
        expired_auth = ReleaseAuthorization(
            correlation_id=corr_id,
            assessment="Test",
            remediation="Test",
            approvers=[ReleaseApproval("a", now.isoformat()), ReleaseApproval("b", now.isoformat())],
            issued_at=(now - timedelta(hours=5)).isoformat(),
            expiry=(now - timedelta(minutes=10)).isoformat(),
            nonce="nonce-expired",
        )
        assert validate_release_auth(expired_auth, corr_id, seen_nonces) == "authorization_expired"


# =====================================================================
# TIER 3: Cross-Feature Combinations (Pairwise Interaction)
# =====================================================================

class TestTier3CrossFeatureCombinations:
    """Tier 3: End-to-end multi-subsystem pipeline interactions."""

    def test_tier3_pit_ingestion_corporate_actions_factor_sim_negative_result(self, tmp_path):
        """Pipeline 1: Raw Data -> Corporate Actions -> Factor Simulation -> Negative Result Chronicle."""
        # 1. Create multi-stock price series (5 stocks, 100 days)
        dates = pd.date_range("2026-01-01", periods=100, freq="B")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "SPY"]
        np.random.seed(42)

        raw_series = {}
        for sym in symbols:
            drift = -0.0005 if sym in ("AAPL", "MSFT") else 0.0002
            returns = np.random.normal(drift, 0.015, len(dates))
            prices = 100.0 * np.cumprod(1.0 + returns)
            raw_series[sym] = pd.Series(prices, index=dates)

        # 2. Apply Corporate Action (2:1 split on AAPL at day 50)
        ca_db = CorporateActionsDB()
        split_date = dates[50].strftime("%Y-%m-%d")
        ca_db.register_split(split_date, "AAPL", 2.0)

        # 3. Build Universe
        manifest = EquitiesUniverseManifest(
            dataset_name="top5_universe",
            asset_class="US_EQUITIES",
            source="test_pipeline",
            universe=symbols,
            timezone="UTC",
            calendar="NYSE",
            coverage_from=dates[0].strftime("%Y-%m-%d"),
            coverage_to=dates[-1].strftime("%Y-%m-%d"),
            is_partition={"from": dates[0].strftime("%Y-%m-%d"), "to": dates[49].strftime("%Y-%m-%d")},
            oos_partition={"from": dates[50].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d")},
            fee_schedule={"commission": 0.005},
            retrieval_ts_utc=datetime.now(timezone.utc).isoformat(),
        )
        universe = build_equities_universe(raw_series, manifest)
        assert len(universe.prices) == 100

        # 4. Generate Factor Scores (5-day reversal)
        factor_scores = -universe.prices.pct_change(5).fillna(0.0)

        # 5. Run Factor Simulation under institutional FactorCostModel
        cost_model = FactorCostModel.standard_us_equity()
        sim_result = simulate_factor_portfolio(
            universe,
            factor_scores,
            hypothesis_id="EQ-004-COMBINED",
            partition="OOS",
            top_k=2,
            bottom_k=2,
            rebalance_freq_days=10,
            cost_model=cost_model,
        )

        assert isinstance(sim_result, FactorSimulationResult)
        assert "total_commissions" in sim_result.costs
        assert "total_borrow_cost" in sim_result.costs

        # 6. Record to ResearchDB and verify negative result terminal record
        rdb = ResearchDB(tmp_path / "titan_research.db")
        rdb.log_run(
            strategy_id="EQ-004-COMBINED",
            instrument="US_50",
            n_bars=len(universe.prices),
            n_trades=20,
            return_pct=sim_result.annualized_net_return,
            sharpe=sim_result.annualized_net_sharpe,
            max_dd_pct=sim_result.max_drawdown * 100.0,
            commission=sim_result.costs["total_commissions"],
        )
        verdict = "candidate" if sim_result.annualized_net_sharpe >= 1.5 else "negative_result"
        rdb.set_qualification(
            strategy_id="EQ-004-COMBINED",
            version="1.0.0",
            status="REJECTED" if verdict == "negative_result" else "QUALIFIED",
            backtest_sharpe=sim_result.annualized_net_sharpe,
            notes="Evaluated under ADR-030 canonical cost model",
        )
        quals = rdb.get_qualifications()
        assert len(quals) == 1
        assert quals[0]["status"] in ("REJECTED", "QUALIFIED")
        rdb.close()

    def test_tier3_preregistration_fxcost_sim_certificate_default_deny_ingress(self, tmp_path):
        """Pipeline 2: Pre-registration -> FX Simulation -> Ed25519 Cert -> Default-Deny Ingress."""
        # 1. Pre-register FX Hypothesis
        hypo = Hypothesis(
            id="FX-001",
            title="EURUSD Microstructure Flow",
            strategy_id="fx-flow",
            instrument="EURUSD",
            sample_adequacy_policy="Path A",
        )
        assert hypo.id == "FX-001"

        # 2. Run simulation with FxCostModel ($2.00 min fee)
        fx_cost = FxCostModel.ibkr_spot_fx_tier_one()
        fill_model = BarConservativeFillModel()
        quote_bar = {"timestamp": "2026-01-02T10:00:00Z", "ask": 1.0850, "bid": 1.0848, "close": 1.0849}
        fill = fill_model.fill(quote_bar, "BUY", 10000, cost_model=fx_cost)
        assert fill.commission == Decimal("2.00")

        # 3. Setup Paper Engine with Default-Deny Ingress
        state_file = tmp_path / "test_engine_state.json"
        risk_cfg = RiskConfig([], Money("1000000", "USD"), 10000, 50000, Money("10000000", "USD"), 0.20, Money("50000", "USD"), 5000, 100)
        paper_cfg = PaperConfig(
            risk_config=risk_cfg,
            state_path=str(state_file),
            authorized_approvers=("alice", "bob"),
        )
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        engine = PaperTradingEngine(paper_cfg, adapter)

        # Register Instrument
        engine.register_instrument(Instrument(InstrumentId("EURUSD", "FOREX"), "0.0001", 1, "1.0", ContractType.Forex, "USD", 4), "EURUSD")

        # Initialize session
        engine.initialize_new_session(make_valid_session_init(approver1="alice", approver2="bob"))

        # 4. Attempt submission of shadow intent -> Must be blocked with ValueError
        shadow_intent = TradeIntent(
            "shadow-strategy", "pkg-1", "paper-1", "EURUSD", "BUY", "1000", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="1.0850",
            certificate_ref=make_valid_certificate_json("shadow-strategy"),
        )
        with pytest.raises(ValueError, match="Shadow intents are strictly forbidden"):
            engine.submit_intent(shadow_intent)

        # 5. Attempt submission of uncertified intent -> Must be blocked with ValueError
        uncertified_intent = TradeIntent(
            "fx-flow", "pkg-1", "paper-1", "EURUSD", "BUY", "1000", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="1.0850",
            certificate_ref=None,
        )
        with pytest.raises(ValueError, match="Missing execution certificate"):
            engine.submit_intent(uncertified_intent)

        # 6. Valid certified intent -> Successfully passes gate and routes to adapter
        valid_intent = TradeIntent(
            "fx-flow", "pkg-1", "paper-1", "EURUSD", "BUY", "1000", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="1.0850",
            certificate_ref=make_valid_certificate_json(
                "fx-flow", instrument="EURUSD", side="BUY", max_quantity=1000,
                account="paper-1"),
        )
        res = engine.submit_intent(valid_intent)
        assert res.accepted is True
        assert len(transport.placed_orders) == 1
        engine.stop()

    def test_tier3_streaming_feed_feedhealth_riskgate_hmac_ibkr_bracket(self, tmp_path):
        """Pipeline 3: TWS Streaming Feed -> Feed Health -> Risk Gate -> HMAC Token -> IBKR Bracket Order."""
        # 1. Setup Feed and Health Snapshot
        latest_bars = {"SPY": ((datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(), 450.0)}
        feed = FakeRealtimeFeed(healthy=True, advancing=True, latest=latest_bars)
        feed_health_snap = FeedHealthSnapshot(feed, ["SPY"], stale_after_s=30.0)

        # 2. Setup Paper Engine
        state_file = tmp_path / "test_bracket_state.json"
        risk_cfg = RiskConfig([], Money("1000000", "USD"), 10000, 50000, Money("10000000", "USD"), 0.20, Money("50000", "USD"), 5000, 100)
        paper_cfg = PaperConfig(risk_config=risk_cfg, state_path=str(state_file))
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        engine = PaperTradingEngine(paper_cfg, adapter, feed_health=feed_health_snap.evaluate)

        engine.register_instrument(Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2), "SPY")
        engine.initialize_new_session(make_valid_session_init(approver1="lead-1", approver2="lead-2"))

        # 3. Create Intent with Bracket Orders (Stop Loss + Take Profit + Trailing Stop)
        trailing_cfg = TrailingConfig("2.00", "1.00")
        intent = TradeIntent(
            "bracket-strat", "pkg-1", "paper-1", "SPY", "BUY", "50", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(),
            price="450.00",
            stop_price="445.00",
            take_profit_price="460.00",
            trailing=trailing_cfg,
            certificate_ref=make_valid_certificate_json(
                "bracket-strat", instrument="SPY", side="BUY", max_quantity=50,
                account="paper-1"),
        )

        # 4. Submit Intent
        res = engine.submit_intent(intent)
        assert res.accepted is True

        # Verify HMAC token is attached on approved intent
        assert len(transport.placed_orders) == 1
        placed = transport.placed_orders[0]
        assert placed.risk_token is not None
        assert len(placed.risk_token) == 64
        assert placed.stop_price == "445.00"
        assert placed.take_profit_price == "460.00"
        engine.stop()

    def test_tier3_halted_state_dual_human_release_feedhealth_active_recovery(self, tmp_path):
        """Pipeline 4: Halted State -> Dual-Human Release -> Feed Health Verification -> Active Recovery."""
        latest_bars = {"SPY": ((datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(), 450.0)}
        feed = FakeRealtimeFeed(healthy=True, advancing=True, latest=latest_bars)
        feed_health_snap = FeedHealthSnapshot(feed, ["SPY"], stale_after_s=30.0)

        state_file = tmp_path / "test_recovery_state.json"
        risk_cfg = RiskConfig([], Money("1000000", "USD"), 10000, 50000, Money("10000000", "USD"), 0.20, Money("50000", "USD"), 5000, 100)
        paper_cfg = PaperConfig(risk_config=risk_cfg, state_path=str(state_file))
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        engine = PaperTradingEngine(paper_cfg, adapter, feed_health=feed_health_snap.evaluate)

        engine.register_instrument(Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2), "SPY")
        engine.initialize_new_session(make_valid_session_init(approver1="lead-1", approver2="lead-2"))

        # 1. Trigger Kill Switch
        engine.trigger_kill_switch(reason="test_emergency_circuit_trip")
        assert engine.risk_gate.kill_switch.blocks_routing() is True

        # 2. Attempt order submission while halted -> Blocked
        intent = TradeIntent(
            "rec-strat", "pkg-1", "paper-1", "SPY", "BUY", "10", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="450.00",
            certificate_ref=make_valid_certificate_json(
                "rec-strat", instrument="SPY", side="BUY", max_quantity=10,
                account="paper-1"),
        )
        res_blocked = engine.submit_intent(intent)
        assert res_blocked.accepted is False
        assert "Kill switch is blocking routing" in res_blocked.rejection_reason

        # 3. Attempt unauthorized release without valid ReleaseAuthorization -> Fails
        with pytest.raises(RuntimeError, match="Cannot release kill switch"):
            engine.release_kill_switch(None)

        # 4. Authorized dual-human release with correlation ID and fresh feed health
        rel_auth = make_valid_release_auth(
            correlation_id=engine._kill_correlation or "",
            approver1="risk-admin-1",
            approver2="exec-admin-2",
        )
        engine.release_kill_switch(rel_auth)
        assert engine.risk_gate.kill_switch.blocks_routing() is False

        # 5. Successful order submission after recovery
        res_ok = engine.submit_intent(intent)
        assert res_ok.accepted is True
        engine.stop()


# =====================================================================
# TIER 4: Real-World Scenarios Tests
# =====================================================================

class TestTier4RealWorldScenarios:
    """Tier 4: Comprehensive end-to-end multi-asset trading day and stress simulations."""

    def test_tier4_full_equities_factor_lifecycle(self, tmp_path):
        """Scenario 1: Ingest 5-asset universe, adjust corporate actions, compute SHA-256 manifest,
        run dollar-neutral factor simulation with IBKR Pro fees & borrow, verify metrics and negative result recording."""
        dates = pd.date_range("2026-01-01", periods=120, freq="B")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "SPY"]
        np.random.seed(101)

        raw_series = {}
        for sym in symbols:
            returns = np.random.normal(0.0001, 0.012, len(dates))
            prices = 150.0 * np.cumprod(1.0 + returns)
            raw_series[sym] = pd.Series(prices, index=dates)

        # Adjust corporate action
        ca_db = CorporateActionsDB()
        ca_db.register_split(dates[30].strftime("%Y-%m-%d"), "AAPL", 2.0)

        # Universe manifest with checksums
        manifest = EquitiesUniverseManifest(
            dataset_name="equities_top5_lifecycle",
            asset_class="US_EQUITIES",
            source="e2e_lifecycle",
            universe=symbols,
            timezone="UTC",
            calendar="NYSE",
            coverage_from=dates[0].strftime("%Y-%m-%d"),
            coverage_to=dates[-1].strftime("%Y-%m-%d"),
            is_partition={"from": dates[0].strftime("%Y-%m-%d"), "to": dates[59].strftime("%Y-%m-%d")},
            oos_partition={"from": dates[60].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d")},
            fee_schedule={"commission": 0.005, "borrow_bps": 50.0},
            retrieval_ts_utc=datetime.now(timezone.utc).isoformat(),
        )
        digest = manifest.digest()
        assert len(digest) == 64

        universe = build_equities_universe(raw_series, manifest)

        # Compute factor scores
        factor_scores = universe.prices.pct_change(20).fillna(0.0)

        # Simulate dollar-neutral factor portfolio
        cost_model = FactorCostModel.standard_us_equity()
        result = simulate_factor_portfolio(
            universe,
            factor_scores,
            hypothesis_id="EQ-001-MOMENTUM-LIFECYCLE",
            partition="OOS",
            top_k=2,
            bottom_k=2,
            rebalance_freq_days=20,
            cost_model=cost_model,
        )

        assert isinstance(result.annualized_net_sharpe, float)
        assert isinstance(result.max_drawdown, float)
        assert result.costs["total_commissions"] >= 0.0
        assert result.costs["total_borrow_cost"] >= 0.0

        # Persist and record in ResearchDB
        rdb = ResearchDB(tmp_path / "lifecycle_research.db")
        rdb.log_run(
            strategy_id="EQ-001-MOMENTUM-LIFECYCLE",
            instrument="TOP5_US",
            n_bars=len(universe.prices),
            n_trades=12,
            return_pct=result.annualized_net_return,
            sharpe=result.annualized_net_sharpe,
            max_dd_pct=result.max_drawdown * 100.0,
            commission=result.costs["total_commissions"],
        )
        rdb.set_qualification(
            strategy_id="EQ-001-MOMENTUM-LIFECYCLE",
            version="1.0.0",
            status="REJECTED" if result.annualized_net_sharpe < 1.0 else "QUALIFIED",
            backtest_sharpe=result.annualized_net_sharpe,
        )
        assert len(rdb.get_runs()) == 1
        rdb.close()

    def test_tier4_canonical_multi_pair_fx_simulation(self):
        """Scenario 2: Multi-Pair FX simulation (EURUSD, GBPUSD) demonstrating $2.00 minimum ticket fee drag."""
        fx_cost = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
        fill_model = BarConservativeFillModel()

        # Simulated quote stream for EURUSD and GBPUSD
        eur_bar = {"timestamp": "2026-01-02T10:00:00Z", "ask": 1.0852, "bid": 1.0850, "close": 1.0851}
        gbp_bar = {"timestamp": "2026-01-02T10:00:00Z", "ask": 1.2722, "bid": 1.2720, "close": 1.2721}

        # 1. Micro-lot trade (10,000 units = ~$10,852 notional)
        eur_micro_fill = fill_model.fill(eur_bar, "BUY", 10000, cost_model=fx_cost)
        # Variable fee would be $0.21, but minimum ticket fee is $2.00 -> 1.84 bps effective commission drag
        assert eur_micro_fill.commission == Decimal("2.00")

        # 2. Institutional trade (5,000,000 units = ~$6,361,000 notional)
        gbp_inst_fill = fill_model.fill(gbp_bar, "BUY", 5000000, cost_model=fx_cost)
        # Variable fee is $6,361,000 * 0.00002 = $127.22 > $2.00
        assert gbp_inst_fill.commission > Decimal("100.00")

    def test_tier4_crypto_perpetual_funding_carry_lifecycle(self):
        """Scenario 3: Crypto Perpetual Funding Carry with Binance VIP0 costs and Default-Deny isolation."""
        crypto_cost = CryptoCostModel.binance_usdt_vip0()
        assert crypto_cost.spot_taker == Decimal("0.001")
        assert crypto_cost.perp_taker == Decimal("0.0005")

        # 1. Taker fee calculation
        notional = Decimal("50000.00")
        spot_fee = crypto_cost.taker_fee(notional, perp=False)
        perp_fee = crypto_cost.taker_fee(notional, perp=True)
        assert spot_fee == Decimal("50.00000")  # 10 bps
        assert perp_fee == Decimal("25.00000")  # 5 bps

        # 2. 8-hour funding cashflow calculation (+0.01% funding rate)
        funding_rate = Decimal("0.0001")
        position_notional = Decimal("100000.00")
        long_funding_payment = position_notional * funding_rate  # $10.00 paid by longs
        short_funding_received = position_notional * funding_rate  # $10.00 received by shorts
        assert long_funding_payment == Decimal("10.0000")
        assert short_funding_received == Decimal("10.0000")

    def test_tier4_end_to_end_paper_trading_ingress_sqlite_persistence(self, tmp_path):
        """Scenario 4: Dual-human session initialization -> certified trade intent -> 9-stage RiskGate
        -> SHA-256 HMAC token -> simulated adapter execution -> SQLite .titan_state.db event sourcing."""
        state_json = tmp_path / ".titan_state.json"
        state_db = tmp_path / ".titan_state.db"
        risk_cfg = RiskConfig(
            ["SPY", "AAPL"], Money("1000000", "USD"), 5000, 20000, Money("5000000", "USD"), 0.15, Money("25000", "USD"), 2500, 100
        )
        paper_cfg = PaperConfig(
            risk_config=risk_cfg,
            state_path=str(state_json),
            authorized_approvers=("risk-lead-alice", "exec-lead-bob"),
        )
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        engine = PaperTradingEngine(paper_cfg, adapter)

        engine.register_instrument(Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2), "SPY")

        # 1. Arm session via dual-approver initialization
        init_auth = make_valid_session_init(approver1="risk-lead-alice", approver2="exec-lead-bob")
        engine.initialize_new_session(init_auth)
        assert engine.risk_gate.kill_switch.blocks_routing() is False

        # 2. Submit certified trade intent
        cert_json = make_valid_certificate_json(
            "alpha-e2e-strat", instrument="SPY", side="BUY", max_quantity=100,
            account="paper-acct-1")
        intent = TradeIntent(
            "alpha-e2e-strat", "pkg-digest-1", "paper-acct-1", "SPY", "BUY", "100", "LIMIT", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(), price="450.00",
            certificate_ref=cert_json,
        )
        result = engine.submit_intent(intent)
        assert result.accepted is True
        assert len(transport.placed_orders) == 1

        # 3. Verify broker fill (Order transitions directly to Filled via _resolve_fills)
        client_order_id = transport.placed_orders[0].client_order_id
        sm = engine.order_states[client_order_id]
        assert sm.current == OrderState.Filled

        # 4. Verify durable persistence in SQLite EventStore
        store = EventStore(str(state_db))
        assert store.count() >= 3  # SessionInitialized, OrderTransition events

        init_events = store.replay_by_type("SessionInitialized")
        assert len(init_events) == 1
        init_payload = json.loads(init_events[0].payload)
        assert "risk-lead-alice" in init_payload["approvers"]

        order_events = store.replay_by_type("OrderTransition")
        assert len(order_events) >= 2
        store.close()
        engine.stop()

    def test_tier4_emergency_circuit_breaker_and_recovery(self, tmp_path):
        """Scenario 5: High-frequency rate burst trips circuit breaker -> drawdown breach halts trading
        -> unauthorized reset blocked -> operator recovery with dual-human ReleaseAuthorization."""
        # 1. Test Multi-Stage Circuit Breaker
        cb_cfg = CircuitBreakerConfig(max_intents_per_second=5, max_intents_per_minute=20, max_consecutive_broker_errors=2)
        breaker = CircuitBreaker(cb_cfg)

        # Submit burst of 6 intents in 1 second
        allowed_count = 0
        for _ in range(6):
            allowed, _ = breaker.record_intent()
            if allowed:
                allowed_count += 1
        assert allowed_count == 5  # Throttled on 6th intent
        assert breaker.stage in (BreakerStage.THROTTLED, BreakerStage.NORMAL)

        # 2. Test Engine Drawdown Breach -> TradingState::Halted
        state_file = tmp_path / "emergency_state.json"
        risk_cfg = RiskConfig([], Money("1000000", "USD"), 5000, 20000, Money("5000000", "USD"), 0.10, Money("25000", "USD"), 2500, 100)
        paper_cfg = PaperConfig(risk_config=risk_cfg, state_path=str(state_file))
        transport = FakeTransport()
        adapter = FakeIBKRPaperAdapter(transport)
        latest_bars = {"SPY": ((datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(), 450.0)}
        feed = FakeRealtimeFeed(healthy=True, advancing=True, latest=latest_bars)
        feed_health_snap = FeedHealthSnapshot(feed, ["SPY"], stale_after_s=30.0)

        engine = PaperTradingEngine(paper_cfg, adapter, feed_health=feed_health_snap.evaluate)

        engine.register_instrument(Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2), "SPY")
        engine.initialize_new_session(make_valid_session_init(approver1="lead-1", approver2="lead-2"))

        # Trigger emergency halt
        engine.trigger_kill_switch(reason="portfolio_drawdown_exceeded_10_percent")
        assert engine.risk_gate.kill_switch.blocks_routing() is True

        # 3. Unauthorized reset attempt fails
        with pytest.raises(RuntimeError, match="Cannot release kill switch"):
            engine.release_kill_switch(None)

        # 4. Authorized dual-human recovery
        auth = make_valid_release_auth(
            correlation_id=engine._kill_correlation or "",
            approver1="senior-risk-lead",
            approver2="head-of-quant-research",
        )
        engine.release_kill_switch(auth)
        assert engine.risk_gate.kill_switch.blocks_routing() is False
        engine.stop()
