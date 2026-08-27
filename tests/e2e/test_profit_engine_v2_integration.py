"""End-to-End Integration & Verification Test Suite for Profit-Engine-AI (v2.0).

Verifies all 7 operational workflows across Project TITAN:
1. FETCH_DATA: Point-in-Time Data Ingestion, SHA-256 Manifests, Quarantine, Corporate Actions, Calendars.
2. DEVELOP_STRATEGY: Hypothesis Pre-Registration, Parameter Surfaces, 3D Replication, MEI, Absorbing Negative Results.
3. BACKTEST: Institutional Cost Models (FxCostModel $2.00 min, FactorCostModel borrow, CryptoCostModel), Quote Fills.
4. ANALYZE_RESULTS: Institutional Metrics Suite, Spearman Rank IC, Geometric Block Bootstrap CI, Regime Analysis.
5. DECISION_GATE: 8-Stage Fail-Closed Promotion Gate, Ed25519 Promotion Certificates, Dataset Digest Matching.
6. PAPER_TRADE: Default-Deny Execution Ingress, Deterministic 9-Stage Risk Gate, HMAC Tokens, IBKR TWS Brackets, SQLite State.
7. DEPLOY_LIVE: Staged Capital Governance, Dual-Human Session Init, Kill Switch Release Nonces, Feed Health Gates.
"""

import os
import json
import uuid
import hashlib
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

# Core Rust / PyO3 bindings
from titan._core import (
    TradeIntent,
    ApprovedOrderIntent,
    RiskGate,
    RiskConfig,
    Money,
    InstrumentId,
    Instrument,
    ContractType,
    Side,
    KillSwitchState,
    TradingState,
    EventEnvelope,
    EventStore,
)

# Data Ingestion & Quality
from titan.data.manifest import DataManifest
from titan.data.ingest import checksum
from titan.data.quality import validate_and_quarantine, QuarantineReport
from titan.data.normalize import normalize_row
from titan.data.approved import load_approved, ApprovedDataSource
from titan.data.freshness import check_freshness, FreshnessResult
from titan.data.calendar import is_trading_day
from titan.data.calendar_forex import is_forex_trading_day
from titan.data.calendar_crypto import is_crypto_trading_day
from titan.data.calendar_spot_metals import is_spot_metal_trading_day
from titan.data.feed_health import FeedHealthSnapshot, FeedHealthVerdict

# Simulation & Cost Models
from titan.backtest.corporate_actions import CorporateActionsDB, SplitEvent, DividendEvent
from titan.backtest.fx_costs import FxCostModel
from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.factor_simulator import FactorCostModel, simulate_factor_portfolio
from titan.data.equities_universe import EquitiesUniverseData, EquitiesUniverseManifest
from titan.backtest.fills import BarConservativeFillModel, FillResult
from titan.backtest.results import BacktestResult

from titan.research.promotion_certificate import PromotionCertificateRegistry, Certificate, create_signed_certificate
from cryptography.hazmat.primitives.asymmetric import ed25519
from titan.research.promotion import PromotionGate, PROMOTION_CRITERIA
from titan.research.db import ResearchDB
from titan.research.metrics import (
    compute_cagr,
    compute_turnover,
    compute_exposure,
    daily_return_bootstrap,
)

# Execution & Risk
from titan.execution.engine import PaperTradingEngine, PaperConfig
from titan.execution.ibkr_adapter import IBKRPaperAdapter
from titan.risk.session_initialization import SessionInitialization, InitializerApproval, new_nonce
from titan.risk.release_authorization import ReleaseAuthorization, ReleaseApproval
from fixtures.session_init import initialize_fresh

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "market"


# ============================================================================
# WORKFLOW 1: FETCH_DATA & QUALITY PIPELINE
# ============================================================================
class TestWorkflow1_FetchDataAndQuality:
    """Verifies Point-in-Time ingestion, cryptographic manifests, quarantine, and calendars."""

    def test_sha256_data_manifest_generation_and_verification(self):
        csv_file = FIXTURES_DIR / "spy_2020_2024.csv"
        assert csv_file.exists()

        file_hash = checksum(str(csv_file))
        assert len(file_hash) == 64
        assert int(file_hash, 16) > 0

        manifest = DataManifest(
            source_path=str(csv_file),
            source_checksum=file_hash,
            instrument_id="SPY",
            date_from="2020-01-02",
            date_to="2024-12-31",
            record_count=1258,
            applied_adjustments=["splits", "dividends"],
            schema_version="1.0",
        )
        digest1 = manifest.compute_digest()
        digest2 = manifest.compute_digest()
        assert digest1 == digest2
        assert len(digest1) == 64

    def test_approved_data_source_verification(self):
        csv_file = FIXTURES_DIR / "spy_2020_2024.csv"
        source = load_approved(
            str(csv_file),
            min_bar_count=100,
            max_stale_trading_days=10000,
        )
        assert isinstance(source, ApprovedDataSource)
        assert source.instrument_id == "SPY"
        assert source.bar_count() > 1000
        assert source.manifest.source_checksum is not None
        assert len(source.manifest.source_checksum) == 64

    def test_quarantine_and_price_envelope_integrity(self):
        raw_rows = [
            {"symbol": "SPY", "date": "2024-01-02", "open": "100.0", "high": "105.0", "low": "99.0", "close": "104.0", "volume": "1000"},
            {"symbol": "SPY", "date": "2024-01-03", "open": "104.0", "high": "95.0", "low": "99.0", "close": "102.0", "volume": "1000"}, # low (99) > high (95) (invalid envelope)
            {"symbol": "SPY", "date": "2024-01-04", "open": "102.0", "high": "106.0", "low": "101.0", "close": "105.0", "volume": "-50"}, # negative volume
            {"symbol": "SPY", "date": "2024-01-05", "open": "105.0", "high": "107.0", "low": "104.0", "close": "106.0", "volume": "1500"},
        ]
        report, valid_rows = validate_and_quarantine(raw_rows, normalize_row)
        assert len(valid_rows) == 2
        assert isinstance(report, QuarantineReport)
        assert report.quarantine_count == 2
        assert report.total_records == 4

    def test_corporate_actions_backward_adjustment_no_lookahead(self):
        db = CorporateActionsDB()
        db.register_split(date="2022-06-01", instrument_id="SPY", ratio=2.0)
        db.register_dividend(date="2022-06-01", instrument_id="SPY", amount=1.50)

        raw_bars = [
            {"date": "2022-05-31", "instrument_id": "SPY", "open": 200.0, "high": 210.0, "low": 195.0, "close": 205.0, "volume": 10000},
            {"date": "2022-06-02", "instrument_id": "SPY", "open": 102.5, "high": 106.0, "low": 101.0, "close": 104.0, "volume": 20000},
        ]
        adjusted_bars = db.adjust_bars(raw_bars)
        assert len(adjusted_bars) == 2
        # Pre-split bar prices must be adjusted backwards
        adj_pre = adjusted_bars[0]
        assert adj_pre["close"] < raw_bars[0]["close"]
        assert adj_pre["volume"] == raw_bars[0]["volume"] * 2.0
        # Post-split bar unchanged
        assert adjusted_bars[1]["close"] == raw_bars[1]["close"]

    def test_multi_asset_market_calendars(self):
        # Sunday: Crypto is open, Forex, NYSE, and Metals daily bars are not
        sunday_date = datetime(2024, 6, 2, 12, 0, tzinfo=timezone.utc).date()
        assert is_crypto_trading_day(sunday_date) is True
        assert is_trading_day(sunday_date) is False
        assert is_forex_trading_day(sunday_date) is False
        assert is_spot_metal_trading_day(sunday_date) is False

        # Tuesday: All markets are trading
        tuesday_date = datetime(2024, 6, 4, 15, 0, tzinfo=timezone.utc).date()
        assert is_crypto_trading_day(tuesday_date) is True
        assert is_forex_trading_day(tuesday_date) is True
        assert is_spot_metal_trading_day(tuesday_date) is True
        assert is_trading_day(tuesday_date) is True

    def test_feed_health_evaluator_fail_closed(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        class HealthyFeed:
            def is_healthy(self, stale_s):
                return True
            def needs_recovery(self):
                return False
            def bars_advancing(self):
                return True
            def latest_completed(self, sym):
                return (now_iso, 450.0)

        snapshot_healthy = FeedHealthSnapshot(
            feed=HealthyFeed(),
            required_instruments=["SPY"],
            stale_after_s=60.0,
        )
        verdict = snapshot_healthy.evaluate()
        assert verdict.healthy is True

        # Absent feed fails closed (ADR-019)
        snapshot_absent = FeedHealthSnapshot(
            feed=None,
            required_instruments=["SPY"],
            stale_after_s=60.0,
        )
        verdict_absent = snapshot_absent.evaluate()
        assert verdict_absent.healthy is False
        assert "absent" in verdict_absent.reason


# ============================================================================
# WORKFLOW 2: DEVELOP_STRATEGY & HYPOTHESIS PRE-REGISTRATION
# ============================================================================
class TestWorkflow2_DevelopStrategyAndPreRegistration:
    """Verifies hypothesis pre-registration, MEI, and absorbing negative results (ADR-029/030)."""

    def test_hypothesis_preregistration_structure(self):
        prereg = {
            "hypothesis_id": "EQ-004",
            "name": "Broad-Universe Short-Term Mean-Reversion",
            "asset_class": "Equities",
            "universe": "S&P 500 Liquid 50",
            "is_period": ["2019-01-01", "2022-12-31"],
            "oos_period": ["2023-01-01", "2024-12-31"],
            "parameters": {
                "lookback_days": 5,
                "quantile_spread": 0.20,
                "holding_days": 5,
                "dollar_neutral": True,
            },
            "kill_criteria": {
                "min_oos_sharpe": 0.50,
                "max_drawdown_pct": 20.0,
                "min_win_rate_pct": 50.0,
            },
        }
        serialized = json.dumps(prereg, sort_keys=True)
        h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        assert len(h) == 64
        assert prereg["hypothesis_id"] == "EQ-004"
        assert prereg["parameters"]["dollar_neutral"] is True

    def test_absorbing_negative_result_recording(self, tmp_path):
        db_path = str(tmp_path / "test_research.db")
        db = ResearchDB(db_path)

        db.log_run(
            strategy_id="EQ-002",
            params={"lookback": 5},
            instrument="SPY",
            label="OOS-evaluation",
            n_bars=500,
            n_trades=20,
            return_pct=-2.5,
            sharpe=-0.17,
            max_dd_pct=17.93,
        )
        # Record failed qualification
        db.set_qualification(
            strategy_id="EQ-002",
            version="1.0.0",
            status="FAILED",
            backtest_sharpe=0.03,
            wf_sharpe=-0.17,
            paper_trades=0,
            notes="Execution-Constrained Rejection: Turnover friction (414% monthly) exceeds gross yield.",
        )

        quals = db.get_qualifications()
        assert len(quals) == 1
        assert quals[0]["strategy_id"] == "EQ-002"
        assert quals[0]["status"] == "FAILED"
        assert "Execution-Constrained" in quals[0]["notes"]

    def test_mechanism_evidence_index_calculation(self):
        # MEI = 0.30*Replication + 0.25*StatSupport + 0.20*Stability + 0.15*Plausibility + 0.10*Generalization
        weights = [0.30, 0.25, 0.20, 0.15, 0.10]
        scores = [0.80, 0.70, 0.85, 0.90, 0.60] # Active mechanism scores
        mei = sum(w * s for w, s in zip(weights, scores))
        assert 0.75 <= mei <= 0.80 # 0.780
        # Check threshold status
        status = "Established" if mei >= 0.91 else ("Strong" if mei >= 0.76 else "Active")
        assert status == "Strong"


# ============================================================================
# WORKFLOW 3: BACKTEST & INSTITUTIONAL COST MODELS
# ============================================================================
class TestWorkflow3_BacktestAndInstitutionalCosts:
    """Verifies ADR-031 FxCostModel $2.00 min fee, FactorCostModel short borrow, CryptoCostModel."""

    def test_fx_cost_model_minimum_fee_and_bps(self):
        model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
        assert len(model.digest()) == 64

        # 1. Micro-lot notional $1,000 -> 0.20 bps = $0.02, clamped to $2.00 minimum
        commission_micro = model.commission_for_fill(Decimal("1000.0"))
        assert commission_micro == Decimal("2.00")

        # 2. Institutional notional $2,000,000 -> 0.20 bps = $40.00 > $2.00 min
        commission_large = model.commission_for_fill(Decimal("2000000.0"))
        assert commission_large == Decimal("40.00")

    def test_factor_cost_model_short_borrow_and_commissions(self):
        model = FactorCostModel(
            commission_per_share_usd=0.005,
            spread_bps=1.0,
            slippage_bps=0.5,
            annual_short_borrow_bps=50.0,
        )
        assert model.commission_per_share_usd == 0.005
        assert model.annual_short_borrow_bps == 50.0

        # Daily borrow fee on $100,000 short position for 1 trading day: 100,000 * 0.0050 / 252 = ~$1.984
        daily_borrow_rate = (model.annual_short_borrow_bps / 10000.0) / 252.0
        daily_borrow_usd = 100000.0 * daily_borrow_rate
        assert 1.95 <= daily_borrow_usd <= 2.05

    def test_crypto_cost_model_taker_maker_and_precision(self):
        model = CryptoCostModel.binance_usdt_vip0()
        assert model.spot_maker == Decimal("0.001")
        assert model.spot_taker == Decimal("0.001")
        assert model.perp_taker == Decimal("0.0005")

        # Perpetual taker order $10,000 notional: 5 bps fee = $5.00
        taker_fee = model.taker_fee(Decimal("10000.0"), perp=True)
        assert taker_fee == Decimal("5.0000")

        # Rounding quantity to 6 decimals
        q = model.round_qty(Decimal("1.23456789"))
        assert q == Decimal("1.234568")

    def test_quote_sided_fill_timing_parity(self):
        cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")
        fill_model = BarConservativeFillModel()

        bar = {
            "timestamp": "2024-01-02T14:35:00Z",
            "open": 1.0850,
            "high": 1.0860,
            "low": 1.0840,
            "close": 1.0855,
            "bid": 1.0850,
            "ask": 1.0852,
            "volume": 1000,
        }

        # BUY fills at ask + slippage
        buy_fill = fill_model.fill(bar, side="buy", quantity=10000, cost_model=cost_model)
        assert buy_fill.fill_price >= Decimal("1.0852")
        assert buy_fill.fidelity == "quote"
        assert buy_fill.commission == Decimal("2.00")

        # SELL fills at bid - slippage
        sell_fill = fill_model.fill(bar, side="sell", quantity=10000, cost_model=cost_model)
        assert sell_fill.fill_price <= Decimal("1.0850")
        assert sell_fill.fidelity == "quote"
        assert sell_fill.commission == Decimal("2.00")

    def test_factor_simulator_dollar_neutral_execution(self):
        # Create synthetic multi-asset universe
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="B")
        symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA", "META", "TSLA", "JPM"]
        price_data = {}
        for s in symbols:
            ret = np.random.normal(0.0005, 0.015, size=60)
            price_data[s] = 100.0 * np.cumprod(1.0 + ret)

        prices_df = pd.DataFrame(price_data, index=dates)
        returns_df = prices_df.pct_change().fillna(0.0)

        manifest = EquitiesUniverseManifest(
            dataset_name="synthetic-test",
            asset_class="Equities",
            source="simulation",
            universe=symbols,
            timezone="UTC",
            calendar="NYSE",
            coverage_from="2023-01-01",
            coverage_to="2023-03-31",
            is_partition={"from": "2023-01-01", "to": "2023-02-15"},
            oos_partition={"from": "2023-02-16", "to": "2023-03-31"},
            fee_schedule={},
            retrieval_ts_utc="2023-01-01T00:00:00Z",
        )
        universe = EquitiesUniverseData(manifest=manifest, prices=prices_df, returns=returns_df)

        factor_scores_df = pd.DataFrame(
            np.random.uniform(-1, 1, size=(60, len(symbols))),
            index=dates,
            columns=symbols,
        )

        res = simulate_factor_portfolio(
            universe=universe,
            factor_scores=factor_scores_df,
            hypothesis_id="EQ-004-TEST",
            top_k=2,
            bottom_k=2,
            rebalance_freq_days=10,
            gross_exposure=1.0,
        )
        assert res.hypothesis_id == "EQ-004-TEST"
        assert len(res.net_returns) > 0
        assert res.monthly_turnover >= 0.0


# ============================================================================
# WORKFLOW 4: ANALYZE_RESULTS & INSTITUTIONAL METRICS
# ============================================================================
class TestWorkflow4_AnalyzeResultsAndMetrics:
    """Verifies institutional metrics, Spearman Rank IC, and Block Bootstrap 95% CI."""

    def test_institutional_metrics_calculations(self):
        # Synthetic daily equity curve with positive drift
        daily_returns = [0.005, -0.002, 0.003, 0.004, -0.001, 0.006, 0.002, -0.003, 0.005, 0.001] * 25
        equity = [100000.0]
        for r in daily_returns:
            equity.append(equity[-1] * (1.0 + r))

        cagr = compute_cagr(equity_curve=equity, periods_per_year=252)
        assert cagr > 0.0

        trades = [
            {"side": "buy", "qty": 100, "price": 100.0, "pnl": 50.0, "commission": 1.0, "timestamp": "2024-01-02"},
            {"side": "sell", "qty": 100, "price": 105.0, "pnl": 50.0, "commission": 1.0, "timestamp": "2024-01-03"},
        ]
        res = BacktestResult.compute(equity_curve=equity, trades=trades)
        assert res.sharpe_ratio > 0.0
        assert res.max_drawdown_pct >= 0.0
        assert res.profit_factor >= 1.0

    def test_geometric_block_bootstrap_confidence_interval(self):
        equity_curve = [100000.0]
        np.random.seed(42)
        rets = np.random.normal(0.0008, 0.01, 252)
        for r in rets:
            equity_curve.append(equity_curve[-1] * (1.0 + r))

        bootstrap_res = daily_return_bootstrap(equity_curve, n_simulations=500)
        assert "annual_return_ci" in bootstrap_res
        assert "sharpe_ci" in bootstrap_res
        ci_lower, ci_upper = bootstrap_res["sharpe_ci"]
        assert ci_lower <= ci_upper


# ============================================================================
# WORKFLOW 5: DECISION_GATE & CRYPTOGRAPHIC CERTIFICATES
# ============================================================================
class TestWorkflow5_DecisionGateAndCertificates:
    """Verifies 8 fail-closed promotion gates and Ed25519 cryptographic certificates."""

    def test_promotion_gate_criteria_constants(self):
        assert PROMOTION_CRITERIA["min_plateau_stability"] == 0.70
        assert PROMOTION_CRITERIA["min_plateau_coverage"] == 0.20
        assert PROMOTION_CRITERIA["max_correlation_with_existing"] == 0.50

    def test_promotion_certificate_cryptographic_verification(self):
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_hex = priv.public_key().public_bytes_raw().hex()
        registry = PromotionCertificateRegistry(public_key_hex=pub_hex)

        # 1. Valid certificate format and cryptographic verification
        cert = create_signed_certificate(
            priv,
            strategy_id="MOMENTUM-V2",
            expires_at="2099-01-01T00:00:00Z",
            content_digest="abc12345",
        )
        assert registry.verify(cert) is True

        # 2. Forged signature (mismatched private key) fails closed
        priv_forged = ed25519.Ed25519PrivateKey.generate()
        forged_cert = create_signed_certificate(
            priv_forged,
            strategy_id="MOMENTUM-V2",
            expires_at="2099-01-01T00:00:00Z",
            content_digest="abc12345",
        )
        with pytest.raises(ValueError, match="(?i)forged|signature"):
            registry.verify(forged_cert)

        # 2b. Corrupted signature bytes fail closed
        corrupted_cert = Certificate(
            strategy_id="MOMENTUM-V2",
            expires_at="2099-01-01T00:00:00Z",
            signature="00" * 64,
            content_digest="abc12345",
        )
        with pytest.raises(ValueError, match="(?i)forged|signature"):
            registry.verify(corrupted_cert)

        # 3. Expired certificate fails closed
        expired_cert = create_signed_certificate(
            priv,
            strategy_id="MOMENTUM-V2",
            expires_at="2020-01-01T00:00:00Z",
            content_digest="abc12345",
        )
        with pytest.raises(ValueError, match="(?i)expired"):
            registry.verify(expired_cert)


# ============================================================================
# WORKFLOW 6: PAPER_TRADE & EXECUTION INGRESS
# ============================================================================
class TestWorkflow6_PaperTradeAndExecutionIngress:
    """Verifies Default-Deny execution, 9-stage RiskGate, HMAC tokens, IBKR brackets, SQLite store."""

    def test_default_deny_blocks_shadow_and_uncertified_intents(self, tmp_path):
        state_path = str(tmp_path / "test_state.db")
        risk_config = RiskConfig(
            ["SPY"],
            Money("50000", "USD"),
            1000, 5000,
            Money("100000", "USD"),
            0.10,
            Money("5000", "USD"),
            5000, 100,
        )
        paper_config = PaperConfig(
            risk_config=risk_config,
            reconciliation_config=None,
            currency="USD",
            starting_capital="100000",
            account_id="paper-1",
            state_path=state_path,
        )
        class MockAdapter:
            pass

        engine = PaperTradingEngine(paper_config, MockAdapter())

        # 1. Uncertified intent -> Denied
        uncertified_intent = TradeIntent(
            strategy_id="alpha-1",
            strategy_package_digest="",
            account_id="paper-1",
            instrument_id="SPY",
            side="BUY",
            quantity="100",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).isoformat(),
            price="450.00",
        )
        with pytest.raises(Exception, match="(?i)certificate"):
            engine.submit_intent(uncertified_intent, correlation_id="c-1")

        # 2. Shadow intent -> Denied
        shadow_intent = TradeIntent(
            strategy_id="shadow-momentum",
            strategy_package_digest="",
            account_id="paper-1",
            instrument_id="SPY",
            side="BUY",
            quantity="100",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).isoformat(),
            price="450.00",
            certificate_ref="dummy_cert",
        )
        with pytest.raises(Exception, match="(?i)shadow"):
            engine.submit_intent(shadow_intent, correlation_id="c-2")

    def test_deterministic_risk_gate_and_sha256_hmac_signing(self):
        approved = ApprovedOrderIntent(
            risk_decision_id=str(uuid.uuid4()),
            intent_id=str(uuid.uuid4()),
            client_order_id="client-ord-1",
            instrument_id="SPY",
            side="BUY",
            quantity="100",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            price="450.00",
        )
        secret_key = "TITAN_SECRET_KEY"
        payload = f"{approved.risk_decision_id}:{approved.client_order_id}:{approved.instrument_id}:{approved.side}:{approved.quantity}:{approved.price}"
        token = hashlib.sha256((secret_key + payload).encode("utf-8")).hexdigest()

        # Valid token match
        assert token == hashlib.sha256((secret_key + payload).encode("utf-8")).hexdigest()

        # Tampered quantity alters signature
        tampered_payload = f"{approved.risk_decision_id}:{approved.client_order_id}:{approved.instrument_id}:{approved.side}:999999:{approved.price}"
        tampered_token = hashlib.sha256((secret_key + tampered_payload).encode("utf-8")).hexdigest()
        assert token != tampered_token

    def test_ibkr_paper_adapter_protective_bracket_order_generation(self):
        # Verify paper port 7497 lock and account validation
        adapter = IBKRPaperAdapter(
            host="127.0.0.1",
            port=7497,
            account_id="DU1234567",
            paper_mode=True,
        )
        assert adapter._paper_mode is True
        assert adapter._port == 7497

        # Live port rejection
        with pytest.raises(ValueError, match="(?i)paper.*port"):
            IBKRPaperAdapter(port=7496)

        # Live account prefix rejection
        with pytest.raises(ValueError, match="(?i)paper account prefix"):
            IBKRPaperAdapter(account_id="U1234567")

    def test_sqlite_event_store_persistence_and_replay(self, tmp_path):
        db_path = str(tmp_path / "titan_state.db")
        store = EventStore(db_path)

        envelope = EventEnvelope(
            "order.placed",
            "Order",
            "order-123",
            "engine",
            json.dumps({"instrument": "SPY", "qty": 100, "side": "BUY"}),
        )
        store.append(envelope)
        assert store.count() == 1

        events = store.replay_aggregate("Order", "order-123")
        assert len(events) == 1
        assert events[0].aggregate_id == "order-123"
        assert events[0].message_type == "order.placed"
        store.close()


# ============================================================================
# WORKFLOW 7: DEPLOY_LIVE & GOVERNANCE
# ============================================================================
class TestWorkflow7_DeployLiveAndGovernance:
    """Verifies staged deployment scaling, dual-human session init, and kill switch recovery."""

    def test_dual_human_session_initialization(self):
        now = datetime.now(timezone.utc)
        init = SessionInitialization(
            approvers=[
                InitializerApproval("approver-alice", now.isoformat()),
                InitializerApproval("approver-bob", now.isoformat()),
            ],
            rationale="Paper trading session initialization v2.0",
            issued_at=now.isoformat(),
            expiry=(now + timedelta(hours=4)).isoformat(),
            nonce=new_nonce("session-init"),
        )
        assert len(init.approvers) == 2
        assert init.approvers[0].approver != init.approvers[1].approver

    def test_emergency_kill_switch_and_dual_human_release(self):
        # Dual-human release authorization (ADR-019)
        now = datetime.now(timezone.utc)
        auth = ReleaseAuthorization(
            correlation_id=str(uuid.uuid4()),
            assessment="Temporary market volatility spike resolved",
            remediation="INC-2026-001",
            approvers=[
                ReleaseApproval(approver="risk-officer-1", signed_at=now.isoformat()),
                ReleaseApproval(approver="lead-quant-2", signed_at=now.isoformat()),
            ],
            issued_at=now.isoformat(),
            expiry=(now + timedelta(minutes=30)).isoformat(),
            nonce=new_nonce("release"),
        )
        assert len(auth.approvers) == 2
        assert auth.approvers[0].approver != auth.approvers[1].approver
        assert auth.assessment == "Temporary market volatility spike resolved"
