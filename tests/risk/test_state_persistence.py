"""Tests for risk gate state persistence."""

import pytest
from titan._core import RiskGate, RiskConfig, EventStore, TradingState, KillSwitchState


class TestRiskStatePersistence:
    def test_persist_and_restore_kill_switch(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.kill_switch == KillSwitchState.Triggered

    def test_persist_and_restore_trading_state(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.set_trading_state(TradingState.Halted)
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.trading_state == TradingState.Halted

    def test_defaults_to_halted_with_no_state(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate.load_or_default(config, store)
        assert gate.kill_switch == KillSwitchState.Triggered
        assert gate.trading_state == TradingState.Halted
        assert not gate.trading_state.accepts_intents()

    def test_persisted_state_halts_routing(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.trigger_kill_switch()
        gate.set_trading_state(TradingState.Halted)
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.kill_switch.blocks_routing()
        assert not restored.trading_state.accepts_intents()

    def test_multiple_persists_restores_latest(self):
        store = EventStore(":memory:")
        config = RiskConfig.default()
        gate = RiskGate(config)
        gate.persist_state(store)
        gate.trigger_kill_switch()
        gate.persist_state(store)
        restored = RiskGate.load_or_default(config, store)
        assert restored.kill_switch == KillSwitchState.Triggered
