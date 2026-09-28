"""The operator incident surface must not hold risk authority.

Covers two commands the incident runbook points responders at:

* ``titan risk release`` — releases nothing. Release authority belongs to
  ``PaperTradingEngine.release_kill_switch()`` (ADR-019 / RISK_POLICY.md), which
  cannot run outside a live session because it must reconcile against the broker.
* ``titan recovery restart`` — reports boot state and, per ADR-020, never arms a
  session whose event store was lost.
"""

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from titan._core import (
    EventEnvelope,
    EventStore,
    KillSwitchState,
    RiskConfig,
    RiskGate,
    TradingState,
)

from titan import cli

GATE_ADVANCING_METHODS = (
    "release_initiated",
    "release_completed",
    "_initialize_armed",
    "set_trading_state",
)


def _halted_store(path: Path) -> None:
    """Persist a Triggered/Halted gate, as a halted session's store looks like."""
    store = EventStore(str(path))
    gate = RiskGate(RiskConfig.default())
    gate.trigger_kill_switch()
    gate.persist_state(store)
    store.close()


def _healthy_store(path: Path) -> None:
    """Persist an Armed/Active gate, i.e. a healthy session's snapshot."""
    store = EventStore(str(path))
    gate = RiskGate(RiskConfig.default())
    gate.persist_state(store)
    store.close()


def _reload(path: Path) -> RiskGate:
    store = EventStore(str(path))
    gate = RiskGate.load_or_default(RiskConfig.default(), store)
    store.close()
    return gate


@pytest.fixture
def repo_state(tmp_path, monkeypatch):
    """cwd holding a ``.titan_state.db`` — the path the CLI hardcodes."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / ".titan_state.db"


class TestRiskReleaseHoldsNoAuthority:
    def test_release_cannot_disarm_a_held_kill_switch(self, repo_state):
        _halted_store(repo_state)
        before = _reload(repo_state)
        assert before.kill_switch.blocks_routing()

        result = CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        assert "trading resumed" not in result.output
        after = _reload(repo_state)
        assert after.kill_switch == KillSwitchState.Triggered, (
            "a CLI command resumed routing without ADR-019 authority"
        )
        assert after.kill_switch.blocks_routing()
        assert before.trading_state == after.trading_state

    def test_release_reports_failure_rather_than_success(self, repo_state):
        _halted_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        assert result.exit_code != 0, result.output
        out = result.output.lower()
        assert "not released" in out
        assert "no release authority" in out
        assert "trading resumed" not in out
        assert "scripts/release_kill_switch.py" in result.output

    def test_release_names_the_authorization_prerequisites(self, repo_state):
        _halted_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        out = result.output.lower()
        for prerequisite in ("two", "reconcil", "health"):
            assert prerequisite in out, f"release guidance omitted {prerequisite!r}"

    def test_release_reports_the_trigger_correlation_when_present(self, repo_state):
        """The operator needs this id for scripts/release_kill_switch.py."""
        _halted_store(repo_state)
        store = EventStore(str(repo_state))
        store.append(EventEnvelope(
            "KillSwitchTriggered", "RiskControl", "ks-abc123", "titan_python",
            json.dumps({"ts": "2026-09-29T00:00:00+00:00",
                        "reason": "critical_reconcile_drift",
                        "correlation_id": "ks-abc123"}),
        ))
        store.close()

        result = CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        assert "ks-abc123" in result.output
        assert "critical_reconcile_drift" in result.output

    def test_release_writes_no_events_to_the_durable_store(self, repo_state):
        """A read-only command must not append RiskStateSnapshot rows.

        The old implementation's ``persist_state`` wrote Released/Active into the
        shared store, so the NEXT session booted ready to route (ADR-020 loss).
        """
        _halted_store(repo_state)
        with sqlite3.connect(repo_state) as conn:
            rows_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        with sqlite3.connect(repo_state) as conn:
            rows_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert rows_after == rows_before

    def test_release_on_an_unheld_switch_is_a_no_op(self, repo_state):
        _healthy_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["risk", "release"], input="y\n")

        assert result.exit_code == 0, result.output
        after = _reload(repo_state)
        assert not after.kill_switch.blocks_routing()

    def test_no_cli_command_can_advance_the_gate_toward_trading(self):
        """Structural lock: a future command must not re-acquire release authority."""
        source = Path(cli.__file__).read_text(encoding="utf-8")
        found = [name for name in GATE_ADVANCING_METHODS if name in source]
        assert found == [], f"cli.py calls gate-advancing methods directly: {found}"


class TestRecoveryRestart:
    def test_restart_runs_at_all(self, repo_state):
        """Guards the TypeError that made this command permanently dead."""
        _halted_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["recovery", "restart"])

        assert result.exit_code == 0, result.output
        assert "System state:" in result.output

    def test_restart_forces_halted_on_a_lost_event_store(self, tmp_path, monkeypatch):
        """ADR-020: an empty store is never interpreted as safe to trade."""
        monkeypatch.chdir(tmp_path)
        # No .titan_state.db in cwd: the recovery run creates an empty store.

        result = CliRunner().invoke(cli.cli, ["recovery", "restart"])

        assert result.exit_code == 0, result.output
        assert "HALTED" in result.output
        assert "ACTIVE" not in result.output

    def test_restart_reads_the_store_path_it_is_given(self, repo_state):
        """The default path must be the real file, not an in-memory store."""
        _healthy_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["recovery", "restart"])

        assert result.exit_code == 0, result.output
        assert "ACTIVE" in result.output, (
            "restart recovered from :memory: instead of the on-disk store"
        )

    def test_restart_never_reports_active_while_the_switch_is_held(self, repo_state):
        """A non-empty store is not proof that routing may resume (ADR-020).

        Before this guard a halted-but-intact store reconciled clean against the
        placeholder adapter and boot recovery reported ACTIVE, because a
        SimulatedAdapter always agrees with an empty reconstructed portfolio.
        """
        _halted_store(repo_state)

        result = CliRunner().invoke(cli.cli, ["recovery", "restart"])

        assert result.exit_code == 0, result.output
        assert "ACTIVE" not in result.output
        assert "kill switch held" in result.output

    def test_restart_does_not_modify_the_durable_store(self, repo_state):
        _halted_store(repo_state)
        with sqlite3.connect(repo_state) as conn:
            rows_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        CliRunner().invoke(cli.cli, ["recovery", "restart"])

        with sqlite3.connect(repo_state) as conn:
            rows_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert rows_after == rows_before


class TestBootTransitionIsFailClosed:
    def test_recover_reports_state_loss(self, tmp_path):
        from titan.recovery.restart import recover_from_event_store

        fresh = recover_from_event_store(str(tmp_path / "fresh.db"))
        assert fresh["store_was_empty"] is True

    def test_recover_reports_state_loss_false_after_events_exist(self, tmp_path):
        from titan.recovery.restart import recover_from_event_store

        path = str(tmp_path / "used.db")
        _halted_store(Path(path))
        assert recover_from_event_store(path)["store_was_empty"] is False

    def test_state_loss_never_yields_active(self, tmp_path):
        from titan.recovery.restart import (
            reconcile_on_boot,
            recover_from_event_store,
            transition_on_boot,
        )

        state = recover_from_event_store(str(tmp_path / "lost.db"))
        recon = reconcile_on_boot(
            state["portfolio"], state["adapter"], state["recon_engine"])
        assert recon["reconciled"] is True

        outcome = transition_on_boot(
            recon, state["risk_gate"], store_was_empty=True)

        assert outcome.startswith("HALTED")
        assert state["risk_gate"].trading_state == TradingState.Halted

    def test_held_switch_never_yields_active(self, tmp_path):
        from titan.recovery.restart import (
            reconcile_on_boot,
            recover_from_event_store,
            transition_on_boot,
        )

        path = tmp_path / "held.db"
        _halted_store(path)
        state = recover_from_event_store(str(path))
        recon = reconcile_on_boot(
            state["portfolio"], state["adapter"], state["recon_engine"])
        assert recon["reconciled"] is True
        assert state["store_was_empty"] is False

        outcome = transition_on_boot(recon, state["risk_gate"],
                                     store_was_empty=False)

        assert outcome.startswith("HALTED")
        assert "kill switch held" in outcome
        assert state["risk_gate"].trading_state == TradingState.Halted

    def test_healthy_session_still_boots_active(self, tmp_path):
        """The normal restart path is unchanged for two-positional callers."""
        from titan.recovery.restart import (
            reconcile_on_boot,
            recover_from_event_store,
            transition_on_boot,
        )

        path = tmp_path / "healthy.db"
        _healthy_store(path)
        state = recover_from_event_store(str(path))
        recon = reconcile_on_boot(
            state["portfolio"], state["adapter"], state["recon_engine"])
        assert state["store_was_empty"] is False

        assert transition_on_boot(recon, state["risk_gate"]) == "ACTIVE"
