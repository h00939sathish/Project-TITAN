"""Regression tests for the Gate-1 review findings on the strict recovery design.

Covers: malformed-snapshot fail-closed restore (P0-2), nonce replay
reconstruction across restart (P1-6), bounded expiry (P1-7), blank approver
identities (P2-9), and the audited init transaction's refusal durability.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from titan._core import (
    EventEnvelope,
    Money,
    ReconciliationConfig,
    RiskConfig,
)
from titan.execution import PaperConfig, PaperTradingEngine, SimulatedAdapter
from titan.risk.session_initialization import (
    InitializerApproval,
    MAX_INIT_TTL_SECONDS,
    SessionInitialization,
    new_nonce,
    validate,
)

RISK = RiskConfig(
    ["AAPL"], Money("50000", "USD"), 1000, 5000, Money("100000", "USD"),
    0.10, Money("5000", "USD"), 5000, 100,
)


def _config(tmp_path: str, name: str) -> PaperConfig:
    return PaperConfig(
        risk_config=RISK,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="50000",
        account_id="d",
        state_path=os.path.join(tmp_path, name),
    )


def _init(nonce: str, **kw) -> SessionInitialization:
    now = datetime.now(timezone.utc)
    defaults = dict(
        approvers=[InitializerApproval("alice", now.isoformat()),
                   InitializerApproval("bob", now.isoformat())],
        rationale="review regression",
        issued_at=now.isoformat(),
        expiry=(now + timedelta(minutes=15)).isoformat(),
        nonce=nonce,
    )
    defaults.update(kw)
    return SessionInitialization(**defaults)


class TestMalformedSnapshotFailClosed:
    def test_malformed_snapshot_restores_triggered_not_raises(self, tmp_path):
        """P0-2: an unreadable persisted RiskStateSnapshot must resolve to
        Triggered/Halted on restore — never raise, never re-arm."""
        cfg = _config(str(tmp_path), "bad.json")
        engine = PaperTradingEngine(cfg, SimulatedAdapter())
        engine._event_store.append(EventEnvelope(
            "RiskStateSnapshot", "RiskRestore", "system", "titan_python",
            "{definitely-not-json!!!",
        ))
        engine.stop()

        reloaded = PaperTradingEngine(cfg, SimulatedAdapter())
        assert reloaded.risk_gate.kill_switch.is_triggered()
        assert not reloaded.risk_gate.trading_state.accepts_intents()
        assert reloaded.risk_gate.kill_switch.blocks_routing()
        reloaded._event_store.close()

    def test_malformed_state_enum_fails_closed(self, tmp_path):
        """A snapshot whose enum strings are garbage still resolves held."""
        cfg = _config(str(tmp_path), "bad2.json")
        engine = PaperTradingEngine(cfg, SimulatedAdapter())
        payload = json.dumps({
            "message_id": "snap-1",
            "kill_switch_state": "NotARealState",
            "trading_state": "AlsoNotReal",
        })
        engine._event_store.append(EventEnvelope(
            "RiskStateSnapshot", "RiskRestore", "system", "titan_python", payload,
        ))
        engine.stop()

        reloaded = PaperTradingEngine(cfg, SimulatedAdapter())
        assert reloaded.risk_gate.kill_switch.blocks_routing()
        reloaded._event_store.close()


class TestNonceReplaySurvivesRestart:
    def test_seen_nonce_reconstructed_from_durable_events(self, tmp_path):
        """P1-6: the replay-protection set is rebuilt from SessionInitialized
        events, so a restart cannot replay a previously-used nonce."""
        cfg = _config(str(tmp_path), "recon.json")
        engine = PaperTradingEngine(cfg, SimulatedAdapter())
        init = _init(new_nonce("recon"))
        engine.initialize_new_session(init)
        nonce = init.nonce
        engine.stop()

        reloaded = PaperTradingEngine(cfg, SimulatedAdapter())
        assert nonce in reloaded._seen_init_nonces
        with pytest.raises(RuntimeError, match="initialization_replayed"):
            reloaded.initialize_new_session(init)
        reloaded._event_store.close()


class TestBoundedExpiry:
    def test_years_long_expiry_refused(self):
        now = datetime.now(timezone.utc)
        init = _init(new_nonce("long"), expiry=(now + timedelta(days=3650)).isoformat())
        assert validate(init, set()) == "initialization_expiry_unbounded"

    def test_within_window_accepted(self):
        now = datetime.now(timezone.utc)
        init = _init(new_nonce("ok"),
                     expiry=(now + timedelta(seconds=MAX_INIT_TTL_SECONDS - 60)).isoformat())
        assert validate(init, set()) == ""

    def test_expiry_before_issued_at_refused(self):
        now = datetime.now(timezone.utc)
        init = _init(new_nonce("past"), expiry=(now - timedelta(minutes=5)).isoformat())
        assert validate(init, set()) == "initialization_expired"


class TestBlankApprovers:
    def test_blank_approver_does_not_count_as_distinct(self):
        now = datetime.now(timezone.utc)
        init = _init(
            new_nonce("blank"),
            approvers=[InitializerApproval("   ", now.isoformat()),
                       InitializerApproval("bob", now.isoformat())],
        )
        assert validate(init, set()) == "initialization_incomplete"

    def test_two_blanks_refused(self):
        now = datetime.now(timezone.utc)
        init = _init(
            new_nonce("2blank"),
            approvers=[InitializerApproval(" ", now.isoformat()),
                       InitializerApproval("  ", now.isoformat())],
        )
        assert validate(init, set()) == "initialization_incomplete"
