import pytest
from datetime import datetime, timezone
from titan.execution.engine import PaperTradingEngine, PaperConfig
from titan._core import TradeIntent, Money, InstrumentId, RiskConfig

def test_engine_rejects_intent_without_certificate():
    risk_config = RiskConfig(
        ["EURUSD"],
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
        state_path="dummy_state.json",
    )
    class DummyAdapter:
        pass
    engine = PaperTradingEngine(paper_config, DummyAdapter())
    
    intent = TradeIntent(
        strategy_id="test-strategy",
        strategy_package_digest="",
        account_id="paper-1",
        instrument_id="EURUSD",
        side="BUY",
        quantity="10",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).isoformat(),
        price="1.0500",
    )
    
    with pytest.raises(Exception, match="(?i)certificate"):
        engine.submit_intent(intent, correlation_id="test-123")


def test_certificate_validation_failures():
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from titan.research.promotion_certificate import PromotionCertificateRegistry, Certificate, create_signed_certificate
    
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    registry = PromotionCertificateRegistry(public_key_hex=pub_hex)
    
    # 0. Authentic valid certificate
    cert_valid = create_signed_certificate(priv, "test", "2099-01-01T00:00:00Z")
    assert registry.verify(cert_valid) is True
    
    # 1. Missing certificate
    with pytest.raises(Exception, match="(?i)missing"):
        registry.verify(None)
    
    # 2. Forged signature (invalid signature bytes)
    cert_forged = Certificate(strategy_id="test", expires_at="2099-01-01T00:00:00Z", signature="00" * 64)
    with pytest.raises(Exception, match="(?i)forged|signature"):
        registry.verify(cert_forged)

    # 2b. Forged signature (signed with mismatched private key)
    priv_mismatch = ed25519.Ed25519PrivateKey.generate()
    cert_wrong_key = create_signed_certificate(priv_mismatch, "test", "2099-01-01T00:00:00Z")
    with pytest.raises(Exception, match="(?i)forged|signature"):
        registry.verify(cert_wrong_key)
        
    # 3. Expired
    cert_expired = create_signed_certificate(priv, "test", "2000-01-01T00:00:00Z")
    with pytest.raises(Exception, match="(?i)expired"):
        registry.verify(cert_expired)


def test_migration_legacy_qualifications():
    from scripts.migrations.migrate_legacy_qualifications import migrate
    import sqlite3
    import tempfile
    import os
    
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    try:
        # setup dummy DB
        conn = sqlite3.connect(tmp.name)
        conn.execute("CREATE TABLE qualifications (strategy_id TEXT, status TEXT, backtest_sharpe REAL, wf_sharpe REAL, paper_trades INTEGER, backtest_return REAL, wf_return REAL, max_dd_pct REAL)")
        conn.execute("INSERT INTO qualifications VALUES ('strat1', 'QUALIFIED', 1.5, 1.2, 50, 0.1, 0.05, 0.02)")
        conn.commit()
        
        # dry run
        res = migrate(tmp.name, apply=False)
        assert res.modified == 1
        
        # apply
        res = migrate(tmp.name, apply=True)
        assert res.modified == 1
        
        cur = conn.cursor()
        cur.execute("SELECT status, reason FROM qualifications_audit")
        row = cur.fetchone()
        assert row[0] == "RETIRED/INVALIDATED"
        assert "Terminal report" in row[1]
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

def test_sizer_parity():
    from titan.strategies.sizing import Sizer
    
    # Missing conversion rate
    res = Sizer.size(100000, 10, 1.05, None, None, 1, 1)
    assert not res.is_tradable
    assert "missing" in res.reason
    
    # Insufficient allocation for min lot
    # 100k equity, 0.1% alloc = 100 notional. At 1.05 price = 95 shares. Step 100 -> 0.
    res = Sizer.size(100000, 0.1, 1.05, 1.0, None, 100, 100)
    assert not res.is_tradable
    assert "minimum" in res.reason
    
    # Step size floor
    # 100k equity, 10% alloc = 10k notional. At 1.0 price = 10,000 shares.
    res = Sizer.size(100000, 10.0, 1.0, 1.0, None, 3000, 1)
    assert res.is_tradable
    assert res.quantity == 9000  # Floor(10000/3000)*3000 = 9000

def test_engine_rejects_shadow_intent():
    risk_config = RiskConfig(
        ["EURUSD"],
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
        state_path="dummy_state.json",
    )
    class DummyAdapter:
        pass
    engine = PaperTradingEngine(paper_config, DummyAdapter())
    
    intent = TradeIntent(
        strategy_id="shadow-test-strategy",
        strategy_package_digest="",
        account_id="paper-1",
        instrument_id="EURUSD",
        side="BUY",
        quantity="10",
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).isoformat(),
        price="1.0500",
    )
    
    # Normally this intent would fail due to other reasons or be accepted.
    with pytest.raises(ValueError, match="(?i)shadow.*forbidden"):
        engine.submit_intent(intent, correlation_id="test-123")

