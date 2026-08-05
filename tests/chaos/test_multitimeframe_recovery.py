"""Recovery tests for multi-timeframe paper runtime."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fixtures.session_init import initialize_fresh

from titan._core import (
    ContractType,
    Instrument,
    InstrumentId,
    Money,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.execution.engine import PaperConfig, PaperTradingEngine
from tests.adapters.test_ibkr_paper_adapter import FakeIBKRPaperAdapter, FakeTransport


class TestMultiTimeframeRecovery:
    """Restart, disconnect, and drift-halt recovery."""

    @pytest.fixture
    def _base_config(self):
        risk_config = RiskConfig(
            ["SPY", "QQQ"],
            Money("50000", "USD"),
            1000, 5000,
            Money("100000", "USD"),
            0.10,
            Money("5000", "USD"),
            5000, 100,
        )
        return PaperConfig(
            risk_config=risk_config,
            reconciliation_config=ReconciliationConfig(),
            currency="USD",
            starting_capital="100000",
            account_id="test-recovery-1",
            state_path="",
        )

    def test_restart_preserves_portfolio(self, _base_config, tmp_path):
        state_file = tmp_path / "state.json"
        config = _base_config
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        initialize_fresh(engine)
        engine.start()
        for sym in ("SPY",):
            engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        engine.submit_intent(TradeIntent(
            "test", "", "test-recovery-1",
            "SPY", "BUY", "50", "MARKET", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(),
            price="450.00",
        ))

        cash_before = engine.portfolio.get_cash_balance().amount

        engine2 = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        engine2.start()
        engine2.register_instrument(
            Instrument(InstrumentId("SPY", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        assert engine2.portfolio.get_cash_balance().amount == cash_before

    def test_disconnect_does_not_crash_on_restart(self, _base_config, tmp_path):
        state_file = tmp_path / "state.json"
        config = _base_config
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        initialize_fresh(engine)
        engine.start()
        engine.stop()

        engine2 = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        engine2.start()
        assert engine2.portfolio.get_cash_balance().amount == "100000"

    def test_empty_portfolio_reconciles(self, _base_config):
        engine = PaperTradingEngine(_base_config, FakeIBKRPaperAdapter(FakeTransport()))
        initialize_fresh(engine)
        engine.start()
        result = engine.reconcile()
        assert result is not None

    def test_intent_after_reconnect(self, _base_config, tmp_path):
        cfg = _base_config
        cfg.state_path = str(tmp_path / "reconnect_state.json")
        engine = PaperTradingEngine(cfg, FakeIBKRPaperAdapter(FakeTransport()))
        initialize_fresh(engine)
        engine.start()
        engine.stop()

        engine2 = PaperTradingEngine(cfg, FakeIBKRPaperAdapter(FakeTransport()))
        engine2.start()
        for sym in ("QQQ",):
            engine2.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        result = engine2.submit_intent(TradeIntent(
            "test", "", "test-recovery-1",
            "QQQ", "BUY", "10", "MARKET", "DAY", "1.0",
            datetime.now(timezone.utc).isoformat(),
            price="500.00",
        ))
        assert result.accepted

    def test_corrupt_state_halts_routing(self, _base_config, tmp_path):
        state_file = tmp_path / "bad_state.json"
        state_file.write_text('{"portfolio": {"cash": {"amount": "corrupt')
        config = _base_config
        config.state_path = str(state_file)

        # No initialization here ON PURPOSE: this test verifies that a corrupt
        # state file fails closed and halts routing. Initializing would persist
        # an Armed snapshot and bypass the corrupt-state path.
        engine = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        engine.start()
        assert engine.risk_gate.kill_switch.blocks_routing()

    def test_kill_switch_persists_across_restart(self, _base_config, tmp_path):
        state_file = tmp_path / "ks_state.json"
        config = _base_config
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        initialize_fresh(engine)
        engine.start()
        engine.trigger_kill_switch()

        engine2 = PaperTradingEngine(config, FakeIBKRPaperAdapter(FakeTransport()))
        engine2.start()
        assert engine2.risk_gate.kill_switch.blocks_routing()
