"""Tests for recovery automation — restart, reconcile, transition."""

import pytest
from pathlib import Path
from titan._core import (
    RiskGate, RiskConfig, EventStore, PortfolioEngine, Money,
    TradingState, KillSwitchState,
)
from titan.recovery.restart import (
    recover_from_event_store, reconcile_on_boot, transition_on_boot,
)
from titan.execution.simulated_adapter import SimulatedAdapter


class SnapshotFailureAdapter:
    def positions(self, account_id: str):
        raise RuntimeError("positions unavailable")

    def holdings(self, account_id: str):
        raise RuntimeError("holdings unavailable")


class TestRecoverFromEventStore:
    def test_recover_clean_state(self):
        """Recovery with no events produces HALTED state (fail-closed)."""
        state = recover_from_event_store(":memory:")
        assert state["risk_gate"].trading_state == TradingState.Halted
        assert state["risk_gate"].kill_switch == KillSwitchState.Triggered
        assert state["portfolio"] is not None
        assert state["adapter"] is not None

    def test_recover_after_persisted_kill_switch(self, tmp_path: Path):
        """Recovery restores persisted kill switch state."""
        db_path = str(tmp_path / "test_recovery.db")
        store = EventStore(db_path)
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        store.close()
        state = recover_from_event_store(db_path)
        assert state["risk_gate"].kill_switch == KillSwitchState.Triggered

    def test_reconcile_clean_on_boot(self):
        """Clean reconciliation with empty portfolio and no broker positions."""
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        adapter = SimulatedAdapter()
        from titan._core import ReconciliationEngine, ReconciliationConfig
        recon = ReconciliationEngine(ReconciliationConfig(critical_drift_fraction=0.05, warning_drift_fraction=0.01))
        result = reconcile_on_boot(portfolio, adapter, recon)
        assert result["reconciled"] is True
        assert result["has_drift"] is False

    def test_transition_clean_to_active(self):
        """Clean reconciliation transitions to ACTIVE."""
        from titan._core import RiskGate, RiskConfig
        config = RiskConfig.default()
        gate = RiskGate(config)
        state = recover_from_event_store(":memory:")
        result = reconcile_on_boot(state["portfolio"], state["adapter"], state["recon_engine"])
        transition = transition_on_boot(result, gate)
        assert transition == "ACTIVE"

    def test_recover_with_alpaca_adapter(self):
        """Recovery with a real (mocked) AlpacaAdapter uses the injected adapter."""
        from unittest.mock import patch, MagicMock
        from titan.execution.alpaca_adapter import AlpacaAdapter
        from titan._core import KillSwitchState

        db_path = ":memory:"
        store = EventStore(db_path)
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        store.close()

        adapter = AlpacaAdapter(api_key="k", secret_key="s")
        with patch.object(AlpacaAdapter, '_in_regular_session', return_value=True):
            with patch("titan.execution.alpaca_adapter.TradingClient") as mock_tc:
                mock_client = MagicMock()
                mock_client.get_account.return_value = MagicMock(
                    id="test", status="ACTIVE", currency="USD", cash="100000",
                )
                mock_tc.return_value = mock_client

                state = recover_from_event_store(db_path, adapter=adapter)
                assert state["adapter"] is adapter
                assert state["risk_gate"].kill_switch == KillSwitchState.Triggered
                health = state["adapter"].heartbeat()
                assert health.connected is True

    def test_boot_stays_halted_when_broker_truth_is_unavailable(self):
        portfolio = PortfolioEngine("USD", Money("100000", "USD"))
        from titan._core import ReconciliationEngine, ReconciliationConfig
        recon = ReconciliationEngine(ReconciliationConfig(critical_drift_fraction=0.05, warning_drift_fraction=0.01))
        result = reconcile_on_boot(portfolio, SnapshotFailureAdapter(), recon)
        gate = RiskGate(RiskConfig.default())
        assert result["snapshot_fetch_failed"] is True
        assert result["reconciled"] is False
        assert transition_on_boot(result, gate) == "HALTED (broker truth unavailable)"
        assert gate.trading_state == TradingState.Halted
