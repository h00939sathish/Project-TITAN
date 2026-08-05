"""Chaos testing for process restart and recovery."""

import os
import tempfile
import pytest
from titan.recovery.restart import (
    recover_from_event_store,
    reconcile_on_boot,
    transition_on_boot,
)
from titan._core import EventStore, RiskGate, RiskConfig, TradingState, KillSwitchState


def test_process_restart_and_recovery():
    """Test process crash and subsequent recovery from SQLite."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Phase 1: Simulate the "crashed" system.
        # We start an engine, change its state, and then abruptly close it.
        store1 = EventStore(path)
        config = RiskConfig.default()
        gate1 = RiskGate(config)
        
        # Simulate an active lifecycle where a drift or error caused a halt
        gate1.set_trading_state(TradingState.Halted)
        # It was armed initially
        assert gate1.kill_switch == KillSwitchState.Armed
        
        gate1.persist_state(store1)
        store1.close()  # Simulate crash (release locks, forget memory)
        
        del gate1
        del store1
        
        # Phase 2: Recover from the event store
        state = recover_from_event_store(path)
        
        # Verify state was accurately hydrated from SQLite
        assert state["risk_gate"].trading_state == TradingState.Halted
        assert state["risk_gate"].kill_switch == KillSwitchState.Armed
        
        # Phase 3: Reconcile on boot
        # Because the adapter and portfolio have no positions in this mock scenario, 
        # they match exactly (both are empty), meaning no drift.
        recon_result = reconcile_on_boot(state["portfolio"], state["adapter"], state["recon_engine"])
        assert recon_result["has_drift"] is False
        assert recon_result["reconciled"] is True
        
        # Phase 4: Transition on boot
        # Because reconciliation was clean, the system should automatically 
        # transition from HALTED back to ACTIVE.
        final_state = transition_on_boot(recon_result, state["risk_gate"])
        assert final_state == "ACTIVE"
        assert state["risk_gate"].trading_state == TradingState.Active
        
    finally:
        if "state" in locals() and "store" in state:
            state["store"].close()
        if os.path.exists(path):
            os.unlink(path)
