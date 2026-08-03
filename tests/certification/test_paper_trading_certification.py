import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from titan.data.approved import load_approved
from titan.execution.engine import PaperTradingEngine, PaperConfig
from titan.execution.simulated_adapter import SimulatedAdapter, SimFillQuality
from titan._core import (
    PortfolioEngine,
    Money,
    RiskGate,
    RiskConfig,
    TradeIntent,
    ReconciliationEngine,
    ReconciliationDriftSeverity,
    ReconciliationConfig,
    Instrument,
    InstrumentId,
    ContractType,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SPY_15M_PATH = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-30" / "spy_15m.csv"


def test_approved_data_preflight_certification():
    """Verify preflight certification gates on approved market data source."""
    assert SPY_15M_PATH.exists()
    approved = load_approved(
        str(SPY_15M_PATH),
        min_bar_count=100,
        max_stale_trading_days=30,
        require_checksum_match=True,
    )

    assert approved.bar_count() == 1062
    assert approved.instrument_id == "SPY"
    assert approved.manifest.source_checksum is not None


def test_multi_session_paper_execution_and_certification():
    """Verify multi-session paper trading execution cycle with risk token signing and reconciliation."""
    risk_config = RiskConfig(
        ["SPY"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )
    config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="cert-1",
        state_path="",
    )
    adapter = SimulatedAdapter()
    adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
    engine = PaperTradingEngine(config, adapter)
    engine.register_instrument(
        Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
    )

    engine.start()

    # Session 1: Submit TradeIntent
    now_iso = datetime.now(timezone.utc).isoformat()
    intent_1 = TradeIntent("strat-1", "pkg-1", "cert-1", "SPY", "BUY", "10", "MARKET", "DAY", "1.0", now_iso, price="450.00")
    res_1 = engine.submit_intent(intent_1)
    assert res_1.accepted is True
    assert len(res_1.fills) > 0

    # Verify portfolio state
    pos = engine.portfolio.get_position("SPY")
    assert pos is not None
    assert pos.quantity == 10

    # Session 2: Submit second TradeIntent
    intent_2 = TradeIntent("strat-1", "pkg-1", "cert-1", "SPY", "SELL", "5", "MARKET", "DAY", "1.0", now_iso, price="455.00")
    res_2 = engine.submit_intent(intent_2)
    assert res_2.accepted is True
    assert len(res_2.fills) > 0

    # Verify updated position
    pos_2 = engine.portfolio.get_position("SPY")
    assert pos_2.quantity == 5

    # Reconciliation check
    recon_engine = ReconciliationEngine(None)
    recon_result = recon_engine.compare(engine.portfolio, adapter.positions("paper-1").positions, adapter.holdings("paper-1").cash)
    assert recon_result.severity == ReconciliationDriftSeverity.InSync
