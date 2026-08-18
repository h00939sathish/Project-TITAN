"""Full pipeline tests for PaperTradingEngine using SimulatedAdapter."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fixtures.session_init import initialize_fresh

from titan._core import (
    BrokerPosition,
    ContractType,
    EventStore,
    Instrument,
    InstrumentId,
    Money,
    PortfolioEngine,
    ReconciliationConfig,
    ReconciliationDriftSeverity,
    RiskConfig,
    KillSwitchState,
    TradeIntent,
    TradingState,
)
from titan.execution import (
    BrokerBalanceSnapshot,
    BrokerPositionSnapshot,
    EngineStatus,
    PaperConfig,
    PaperTradingEngine,
    SimFillQuality,
    SimulatedAdapter,
)


def _default_config() -> PaperConfig:
    risk_config = RiskConfig(
        ["AAPL", "MSFT"],
        Money("50000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        100,
    )
    return PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="test-1",
        state_path="",
    )


def _make_intent(instrument="AAPL", side="BUY", quantity="100", price=None) -> TradeIntent:
    from datetime import datetime, timezone
    return TradeIntent(
        "test-strat", "test-pkg", "test-1",
        instrument, side, quantity, "MARKET", "DAY", "1.0",
        datetime.now(timezone.utc).isoformat(),
        price=price,
        certificate_ref="test-cert",
    )


class _DivergingAdapter(SimulatedAdapter):
    """An adapter that reports different positions than what was filled."""
    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=[BrokerPosition("MSFT", "LONG", 999)],
            timestamp="2026-01-01T00:00:00Z",
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=Money("999999", "USD"),
            portfolio_value=Money("999999", "USD"),
            buying_power=Money("999999", "USD"),
            equity=Money("999999", "USD"),
            timestamp="2026-01-01T00:00:00Z",
        )


class _SnapshotFailureAdapter(SimulatedAdapter):
    """An adapter that cannot provide the broker truth required to reconcile."""

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        raise RuntimeError("positions unavailable")

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        raise RuntimeError("holdings unavailable")


class TestPaperTradingEngineConstruction:
    def test_engine_creates_with_defaults(self):
        config = _default_config()
        adapter = SimulatedAdapter()
        engine = PaperTradingEngine(config, adapter)
        assert engine.config.account_id == "test-1"

    def test_engine_starts_without_auth(self):
        config = _default_config()
        adapter = SimulatedAdapter()
        engine = PaperTradingEngine(config, adapter)
        try:
            engine.start()
        except Exception:
            pass

    def test_engine_status_before_start(self):
        config = _default_config()
        engine = PaperTradingEngine(config, SimulatedAdapter())
        status = engine.status()
        assert isinstance(status, EngineStatus)
        assert status.cash_balance.amount == "100000"

    def test_engine_config_uses_supplied_instruments(self):
        config = _default_config()
        engine = PaperTradingEngine(config, SimulatedAdapter())
        assert "AAPL" in engine.config.risk_config.instrument_eligibility
        assert "MSFT" in engine.config.risk_config.instrument_eligibility


class TestPaperTradingEngineSubmitIntent:
    def setup_method(self):
        self.config = _default_config()
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.engine = PaperTradingEngine(self.config, self.adapter)
        initialize_fresh(self.engine)
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )

    def test_submit_market_buy_fills_immediately(self):
        result = self.engine.submit_intent(_make_intent())
        assert result.accepted is True
        assert result.broker_order_id is not None
        assert len(result.fills) > 0

    def test_submit_updates_portfolio(self):
        result = self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="150")
        )
        assert result.accepted
        pos = self.engine.portfolio.get_position("AAPL")
        assert pos is not None
        assert pos.quantity == 100

    def test_submit_updates_cash_balance(self):
        result = self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="50", price="100")
        )
        assert result.accepted
        cash = self.engine.portfolio.get_cash_balance()
        assert cash.amount == "95000"

    def test_submit_sell_reduces_position(self):
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="100")
        )
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", side="SELL", quantity="40", price="150")
        )
        pos = self.engine.portfolio.get_position("AAPL")
        assert pos.quantity == 60

    def test_submit_multiple_instruments(self):
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        self.engine.submit_intent(_make_intent(instrument="MSFT", quantity="50", price="400"))
        aapl = self.engine.portfolio.get_position("AAPL")
        msft = self.engine.portfolio.get_position("MSFT")
        assert aapl.quantity == 100
        assert msft.quantity == 50

    def test_submit_returns_position_and_cash(self):
        result = self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="75", price="200")
        )
        assert result.position is not None
        assert result.position.quantity == 75
        assert result.cash_balance is not None

    def test_current_gross_exposure_returns_dollar_value(self):
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        exposure = self.engine._current_gross_exposure()
        assert exposure.amount == "15000"
        assert exposure.currency == "USD"

    def test_current_gross_exposure_multi_instrument(self):
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        self.engine.submit_intent(_make_intent(instrument="MSFT", quantity="50", price="400"))
        exposure = self.engine._current_gross_exposure()
        assert exposure.amount == "35000"
        assert exposure.currency == "USD"

    def test_current_gross_exposure_empty_portfolio(self):
        exposure = self.engine._current_gross_exposure()
        assert exposure.amount == "0"
        assert exposure.currency == "USD"


def _pressure_test_auth(corr):
    from datetime import timedelta
    from titan.risk.release_authorization import (
        ReleaseApproval, ReleaseAuthorization, new_nonce)
    now = datetime.now(timezone.utc).isoformat()
    return ReleaseAuthorization(
        correlation_id=corr or "ks-test",
        assessment="assessment-ref", remediation="remediation-ref",
        approvers=[ReleaseApproval("alice", now), ReleaseApproval("bob", now)],
        issued_at=now,
        expiry=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        nonce=new_nonce("t"),
    )


def _pressure_feed():
    from titan.data.feed_health import FeedHealthVerdict
    return lambda: FeedHealthVerdict(True, "", {}, datetime.now(timezone.utc).isoformat())


class TestPaperTradingEngineRisk:
    def setup_method(self):
        self.config = _default_config()
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.engine = PaperTradingEngine(
            self.config, self.adapter, feed_health=_pressure_feed())
        initialize_fresh(self.engine)
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )

    def test_unknown_instrument_rejected(self):
        result = self.engine.submit_intent(_make_intent(instrument="GOOGL"))
        assert result.accepted is False
        assert result.rejection_reason is not None

    def test_kill_switch_blocks_intents(self):
        self.engine.trigger_kill_switch()
        result = self.engine.submit_intent(_make_intent())
        assert result.accepted is False

    def test_kill_switch_release_allows_intents(self):
        self.engine.trigger_kill_switch()
        self.engine.release_kill_switch(
            _pressure_test_auth(corr=self.engine._kill_correlation))
        result = self.engine.submit_intent(_make_intent())
        assert result.accepted is True

    def test_rejected_intent_returns_reason(self):
        result = self.engine.submit_intent(_make_intent(instrument="GOOGL"))
        assert result.accepted is False
        assert len(result.rejection_reason) > 0

    def test_rejected_intent_does_not_affect_portfolio(self):
        self.engine.submit_intent(_make_intent(instrument="GOOGL"))
        pos = self.engine.portfolio.get_position("GOOGL")
        assert pos is None


class TestPaperTradingEngineReconcile:
    def setup_method(self):
        self.config = _default_config()
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.engine = PaperTradingEngine(self.config, self.adapter)
        initialize_fresh(self.engine)
        self.engine.start()

    def test_reconcile_empty_portfolio(self):
        result = self.engine.reconcile()
        assert result.severity is not None

    def test_reconcile_after_trades(self):
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="150")
        )
        result = self.engine.reconcile()
        assert result.severity is not None

    def test_reconcile_multiple_positions(self):
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="50", price="100"))
        self.engine.submit_intent(_make_intent(instrument="MSFT", quantity="30", price="200"))
        result = self.engine.reconcile()
        assert result.position_drifts is not None

    def test_start_sync_snapshot_failure_triggers_kill_switch(self):
        self.engine.adapter = _SnapshotFailureAdapter()

        self.engine.start(sync_from_broker=True)

        assert self.engine.risk_gate.kill_switch.blocks_routing()


class TestPaperTradingEngineStatus:
    def setup_method(self):
        self.config = _default_config()
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.engine = PaperTradingEngine(self.config, self.adapter, feed_health=_pressure_feed())
        initialize_fresh(self.engine)
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )

    def test_status_reports_active_trading_state(self):
        status = self.engine.status()
        assert status.trading_state is not None

    def test_status_reports_positions(self):
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="150")
        )
        status = self.engine.status()
        assert len(status.positions) >= 1

    def test_status_reports_cash(self):
        self.engine.submit_intent(
            _make_intent(instrument="MSFT", quantity="10", price="400")
        )
        status = self.engine.status()
        assert float(status.cash_balance.amount) < 100000

    def test_status_after_multiple_trades(self):
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        self.engine.submit_intent(_make_intent(instrument="MSFT", quantity="50", price="400"))
        status = self.engine.status()
        assert len(status.positions) == 2

    def test_trigger_kill_switch_updates_status(self):
        self.engine.trigger_kill_switch()
        status = self.engine.status()
        assert status.kill_switch is not None

    def test_release_kill_switch_updates_status(self):
        self.engine.trigger_kill_switch()
        self.engine.release_kill_switch(
            _pressure_test_auth(corr=self.engine._kill_correlation))
        status = self.engine.status()
        assert status.kill_switch is not None

    def test_release_kill_switch_noop_when_never_triggered(self):
        """P0 fix: releasing an Armed (never-triggered) switch is a no-op,
        not an illegal-transition error, and the signal is not consumed."""
        self.engine.release_kill_switch()  # must not raise
        assert not self.engine.risk_gate.kill_switch.blocks_routing()

    def test_release_kill_switch_returns_to_active(self):
        self.engine.trigger_kill_switch()
        self.engine.release_kill_switch(
            _pressure_test_auth(corr=self.engine._kill_correlation))
        assert not self.engine.risk_gate.kill_switch.blocks_routing()
        assert self.engine.risk_gate.trading_state == TradingState.Active

    def test_critical_reconcile_retriggers_switch_after_release(self):
        """A later critical drift must re-halt a released session without crashing."""
        engine = PaperTradingEngine(
            _default_config(), SimulatedAdapter(), feed_health=_pressure_feed())
        initialize_fresh(engine)
        engine.trigger_kill_switch()
        engine.release_kill_switch(
            _pressure_test_auth(corr=engine._kill_correlation))
        assert engine.risk_gate.kill_switch == KillSwitchState.Released

        engine.adapter = _DivergingAdapter()

        result = engine.reconcile()

        assert result.severity == ReconciliationDriftSeverity.Critical
        assert engine.risk_gate.kill_switch == KillSwitchState.Triggered

    def test_release_kill_switch_refuses_on_critical_drift_with_reason(self):
        """P0 fix: release refuses on critical reconcile drift and the error
        carries a structured kill_reason code the session can echo."""
        adapter = _DivergingAdapter()
        engine = PaperTradingEngine(self._config(), adapter, feed_health=_pressure_feed())
        initialize_fresh(engine)
        engine.start()
        engine.trigger_kill_switch()
        with pytest.raises(RuntimeError) as excinfo:
            engine.release_kill_switch(
                _pressure_test_auth(corr=engine._kill_correlation))
        assert "kill_reason=critical_reconcile_drift" in str(excinfo.value)
        # switch remains held — release did not silently succeed
        assert engine.risk_gate.kill_switch.blocks_routing()

    def _config(self):
        return _default_config()


class TestPaperTradingEngineFullPipeline:
    """End-to-end: buy → sell → reconcile, matching the vertical slice test pattern."""

    def setup_method(self):
        self.config = _default_config()
        self.adapter = SimulatedAdapter()
        self.adapter.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
        self.engine = PaperTradingEngine(self.config, self.adapter)
        initialize_fresh(self.engine)

    def test_full_buy_sell_reconcile_cycle(self):
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )

        buy_result = self.engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="150")
        )
        assert buy_result.accepted

        sell_result = self.engine.submit_intent(
            _make_intent(instrument="AAPL", side="SELL", quantity="50", price="160")
        )
        assert sell_result.accepted

        pos = self.engine.portfolio.get_position("AAPL")
        assert pos.quantity == 50

        result = self.engine.reconcile()
        assert result.severity == ReconciliationDriftSeverity.InSync
        assert all(d.quantity_drift == 0 for d in result.position_drifts)

    def test_critical_drift_triggers_kill_switch(self):
        """Diverging adapter data triggers critical drift and kill switch."""
        config = _default_config()
        adapter = _DivergingAdapter()
        engine = PaperTradingEngine(config, adapter)
        initialize_fresh(engine)
        engine.start()
        for sym in ("AAPL", "MSFT"):
            engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        result = engine.reconcile()
        assert result.severity == ReconciliationDriftSeverity.Critical
        assert engine.risk_gate.kill_switch.blocks_routing()

    def test_multiple_buys_accumulate(self):
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="50", price="100"))
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="50", price="150"))
        pos = self.engine.portfolio.get_position("AAPL")
        assert pos.quantity == 100

    def test_full_sell_closes_position(self):
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", side="SELL", quantity="100", price="160")
        )
        pos = self.engine.portfolio.get_position("AAPL")
        assert pos is None or pos.quantity == 0

    def test_status_after_full_cycle(self):
        self.engine.start()
        for sym in ("AAPL", "MSFT"):
            self.engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        self.engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        self.engine.submit_intent(
            _make_intent(instrument="AAPL", side="SELL", quantity="50", price="160")
        )
        status = self.engine.status()
        assert len(status.positions) > 0 or float(status.cash_balance.amount) > 0

    def test_reconcile_with_no_trades(self):
        self.engine.start()
        result = self.engine.reconcile()
        assert len(result.position_drifts) == 0


class TestPaperTradingEngineStatePersistence:
    def test_save_and_load_state(self, tmp_path):
        state_file = tmp_path / "state.json"
        config = _default_config()
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        engine.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        engine.submit_intent(
            _make_intent(instrument="AAPL", quantity="100", price="150")
        )

        cash_before = engine.portfolio.get_cash_balance().amount
        pos_before = engine.portfolio.get_position("AAPL")
        assert pos_before is not None
        assert pos_before.quantity == 100

        engine2 = PaperTradingEngine(config, SimulatedAdapter())
        engine2.start(sync_from_broker=False)
        engine2.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        assert engine2.portfolio.get_cash_balance().amount == cash_before
        pos_after = engine2.portfolio.get_position("AAPL")
        assert pos_after is not None
        assert pos_after.quantity == 100

    def test_load_non_existent_state_uses_starting_capital(self, tmp_path):
        state_file = tmp_path / "nonexistent.json"
        config = _default_config()
        config.state_path = str(state_file)

        # NO initialization here ON PURPOSE: this test verifies fail-closed
        # default recovery over a nonexistent state file (ADR-020). A fresh
        # engine must start Triggered/Halted, never Armed.
        engine = PaperTradingEngine(config, SimulatedAdapter())
        engine.start(sync_from_broker=False)
        assert engine.risk_gate.kill_switch.is_triggered()
        assert not engine.risk_gate.trading_state.accepts_intents()
        assert engine.portfolio.get_cash_balance().amount == "100000"
        assert engine.portfolio.get_position("AAPL") is None

    def test_save_after_submit_intent_persists(self, tmp_path):
        state_file = tmp_path / "state2.json"
        config = _default_config()
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        engine.register_instrument(
            Instrument(InstrumentId("MSFT", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        engine.submit_intent(
            _make_intent(instrument="MSFT", quantity="50", price="400")
        )

        store = EventStore(str(state_file.with_suffix(".db")))
        events = store.replay_by_type("PortfolioState")
        assert len(events) >= 1
        payload = json.loads(events[-1].payload)
        assert payload["portfolio"]["cash"]["amount"] is not None
        assert "MSFT" in payload["portfolio"]["positions"]
        assert payload["portfolio"]["positions"]["MSFT"]["quantity"] == 50
        store.close()

    def test_save_and_load_with_multiple_instruments(self, tmp_path):
        state_file = tmp_path / "state3.json"
        config = _default_config()
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        for sym in ("AAPL", "MSFT"):
            engine.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))
        engine.submit_intent(_make_intent(instrument="MSFT", quantity="50", price="400"))

        engine2 = PaperTradingEngine(config, SimulatedAdapter())
        engine2.start(sync_from_broker=False)
        for sym in ("AAPL", "MSFT"):
            engine2.register_instrument(
                Instrument(InstrumentId(sym, "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            )
        assert engine2.portfolio.get_position("AAPL").quantity == 100
        assert engine2.portfolio.get_position("MSFT").quantity == 50
        assert float(engine2.portfolio.get_cash_balance().amount) < 100000

    def test_empty_state_path_skips_persistence(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = _default_config()
        config.state_path = ""
        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        engine.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        engine.submit_intent(_make_intent(instrument="AAPL", quantity="10", price="100"))
        assert engine.portfolio.get_position("AAPL").quantity == 10
        assert not Path(".titan_state.json").exists()

    def test_event_store_canonical(self, tmp_path):
        """PortfolioState event must be written to EventStore on save."""
        state_file = tmp_path / "state.json"
        config = _default_config()
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        engine.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))

        store = EventStore(str(state_file.with_suffix(".db")))
        events = store.replay_by_type("PortfolioState")
        assert len(events) >= 1
        payload = json.loads(events[-1].payload)
        assert "portfolio" in payload
        assert "intent_counter" in payload
        assert "order_count" in payload
        store.close()

    def test_restart_restores_order_state(self, tmp_path):
        """Order state machines must be correctly reconstructed from EventStore on restart."""
        state_file = tmp_path / "state.json"
        config = _default_config()
        config.state_path = str(state_file)

        engine = PaperTradingEngine(config, SimulatedAdapter())
        initialize_fresh(engine)
        engine.start()
        engine.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )
        result = engine.submit_intent(_make_intent(instrument="AAPL", quantity="100", price="150"))

        orig_states = {oid: sm.current for oid, sm in engine.order_states.items()}

        engine._event_store.close()

        engine2 = PaperTradingEngine(config, SimulatedAdapter())
        engine2.start(sync_from_broker=False)
        engine2.register_instrument(
            Instrument(InstrumentId("AAPL", "STOCK"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        )

        assert len(engine2.order_states) == len(orig_states)
        for oid, expected in orig_states.items():
            assert oid in engine2.order_states
            assert engine2.order_states[oid].current == expected, \
                f"Order {oid}: expected {expected}, got {engine2.order_states[oid].current}"
