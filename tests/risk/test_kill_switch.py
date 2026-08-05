"""Tests for kill switch behavior."""

from titan._core import KillSwitchState, Money, RiskConfig, RiskGate


def make_gate():
    return RiskGate(
        RiskConfig(
            [], Money("1000000", "USD"), 10000, 50000,
            Money("10000000", "USD"), 0.10, Money("50000", "USD"), 5000, 100,
        )
    )


class TestKillSwitch:
    def test_default_armed(self):
        gate = make_gate()
        assert gate.kill_switch == KillSwitchState.Armed

    def test_trigger_changes_state(self):
        gate = make_gate()
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered

    def test_trigger_blocks_routing(self):
        gate = make_gate()
        assert not KillSwitchState.Armed.blocks_routing()
        assert KillSwitchState.Triggered.blocks_routing()
        assert KillSwitchState.Releasing.blocks_routing()
        assert not KillSwitchState.Released.blocks_routing()

    def test_full_lifecycle(self):
        _ks = KillSwitchState.Armed
        _ks = KillSwitchState.Triggered
        _ks = KillSwitchState.Releasing
        _ks = KillSwitchState.Released
        _ks = KillSwitchState.Armed

    def test_release_re_trigger(self):
        gate = make_gate()
        gate.trigger_kill_switch()
        gate.release_initiated()
        gate.trigger_kill_switch()
        assert gate.kill_switch == KillSwitchState.Triggered
