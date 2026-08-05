"""Kill-switch release gate tests (ADR-019 authority + feed-health model)."""

import pytest
from datetime import datetime, timedelta, timezone

from titan._core import Money, ReconciliationConfig, RiskConfig, TradingState
from titan.execution import PaperConfig
from titan.data.feed_health import FeedHealthVerdict
from titan.execution import PaperTradingEngine
from titan.execution import SimulatedAdapter, SimFillQuality
from fixtures.session_init import initialize_fresh

from titan.risk.release_authorization import (
    ReleaseApproval,
    ReleaseAuthorization,
    new_nonce,
)


def _config():
    risk_config = RiskConfig(
        ["AAPL", "MSFT"],
        Money("50000", "USD"), 1000, 5000,
        Money("100000", "USD"), 0.10, Money("5000", "USD"), 5000, 100,
    )
    return PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="50000",
        account_id="paper-1",
        state_path="",
    )


def _adapter():
    a = SimulatedAdapter()
    a.set_default_fill_quality(SimFillQuality.IMMEDIATE_FULL)
    return a


def _auth(corr):
    now = datetime.now(timezone.utc).isoformat()
    return ReleaseAuthorization(
        correlation_id=corr or "ks-test",
        assessment="assessment-ref",
        remediation="remediation-ref",
        approvers=[ReleaseApproval("alice", now), ReleaseApproval("bob", now)],
        issued_at=now,
        expiry=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        nonce=new_nonce("t"),
    )


def _healthy_feed():
    return lambda: FeedHealthVerdict(True, "", {}, datetime.now(timezone.utc).isoformat())


def _feed(healthy=True, reason=""):
    return lambda: FeedHealthVerdict(healthy, reason, {}, datetime.now(timezone.utc).isoformat())


class TestReleaseGate:
    class _Clean:
        severity = None
        position_drifts = []
        cash_drift = 0

    def _triggered_engine(self, feed_fn):
        eng = PaperTradingEngine(_config(), _adapter(), feed_health=feed_fn)
        # Strict recovery (ADR-020): a fresh engine starts fail-closed held;
        # explicitly initialize it (test-only fixture) before arming/trigger.
        initialize_fresh(eng)
        eng.start()
        # Isolate the release-gate logic from adapter/reconcile details: stub a
        # clean reconcile and a healthy adapter so only auth + feed-health +
        # TOCTOU are under test (adapter/reconcile interplay is covered by the
        # existing engine suites).
        eng.reconcile = lambda: TestReleaseGate._Clean()
        eng._check_adapter_health = lambda force=False: True
        eng.trigger_kill_switch()
        return eng

    def test_missing_authorization_refused(self):
        eng = self._triggered_engine(_healthy_feed())
        with pytest.raises(RuntimeError, match="release_not_authorized"):
            eng.release_kill_switch(None)
        assert eng.risk_gate.kill_switch.blocks_routing()

    def test_feed_down_refused(self):
        eng = self._triggered_engine(_feed(healthy=False, reason="feed_stale"))
        with pytest.raises(RuntimeError, match="feed_stale"):
            eng.release_kill_switch(_auth(corr=eng._kill_correlation))
        assert eng.risk_gate.kill_switch.blocks_routing()
        # refusal recorded separately from the (preserved) kill reason
        assert any(r["reason"] == "feed_stale" for r in eng._release_refusals)

    def test_duplicate_nonce_replayed(self):
        eng = self._triggered_engine(_healthy_feed())
        auth = _auth(corr=eng._kill_correlation)
        # consume the nonce once
        eng.release_kill_switch(auth)
        assert not eng.risk_gate.kill_switch.blocks_routing()
        # replaying the same authorization must fail
        eng2 = self._triggered_engine(_healthy_feed())
        eng2._kill_correlation = eng._kill_correlation
        eng2._seen_release_nonces.add(auth.nonce)
        with pytest.raises(RuntimeError, match="authorization_replayed"):
            eng2.release_kill_switch(auth)

    def test_toctou_feed_degrades_before_commit(self):
        calls = {"n": 0}

        def flaky_feed():
            calls["n"] += 1
            # first evaluation (step 3) is healthy; the TOCTOU re-check (step 4)
            # sees the feed degrade -> refuse, never commit.
            if calls["n"] >= 2:
                return FeedHealthVerdict(False, "feed_stale", {},
                                         datetime.now(timezone.utc).isoformat())
            return FeedHealthVerdict(True, "", {}, datetime.now(timezone.utc).isoformat())

        eng = self._triggered_engine(flaky_feed)
        with pytest.raises(RuntimeError, match="feed_stale"):
            eng.release_kill_switch(_auth(corr=eng._kill_correlation))
        # switch was NEVER released (state not committed)
        assert eng.risk_gate.kill_switch.blocks_routing()

    def test_expired_authorization_refused(self):
        eng = self._triggered_engine(_healthy_feed())
        auth = _auth(corr=eng._kill_correlation)
        auth.expiry = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with pytest.raises(RuntimeError, match="authorization_expired"):
            eng.release_kill_switch(auth)
        assert eng.risk_gate.kill_switch.blocks_routing()

    def test_single_approver_refused(self):
        eng = self._triggered_engine(_healthy_feed())
        auth = _auth(corr=eng._kill_correlation)
        auth.approvers = auth.approvers[:1]
        with pytest.raises(RuntimeError, match="authorization_incomplete"):
            eng.release_kill_switch(auth)
        assert eng.risk_gate.kill_switch.blocks_routing()

    def test_correlation_mismatch_refused(self):
        eng = self._triggered_engine(_healthy_feed())
        with pytest.raises(RuntimeError, match="authorization_mismatch"):
            eng.release_kill_switch(_auth(corr="ks-other-incident"))
        assert eng.risk_gate.kill_switch.blocks_routing()

    def test_successful_release(self):
        eng = self._triggered_engine(_healthy_feed())
        eng.release_kill_switch(_auth(corr=eng._kill_correlation))
        assert not eng.risk_gate.kill_switch.blocks_routing()
        assert eng.risk_gate.kill_switch.is_triggered() is False
        assert eng.risk_gate.trading_state == TradingState.Active