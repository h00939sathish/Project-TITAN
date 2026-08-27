"""Execution recovery matrix (P0/P1/P2 verification).

Fault-injection tests for the TradeIntent -> broker fill path. Each test
corresponds to an entry in the post-audit recovery matrix and must fail closed:

    Test 1: fill arrives via poller and/or submit thread — exactly 1 application
    Test 2: partial fill -> broker cancellation — partial position preserved
    Test 3: broker accepts -> network timeout — no retry until outcome resolved
    Test 4: disconnect with open order — state reconciled when visibility returns
    Test 5: concurrent submits — exactly N broker orders, exact accounting
    Test 6: TP + SL bracket race — brackets hard-rejected pending OCA
    Test 7: valid certificate + mismatched scope — hard rejection
    Test 8: crash after send / before acknowledgement — deterministic recovery
    Test 9: TWAP disabled — no import/runtime path available
"""
import json
import threading
from datetime import datetime, timezone

import pytest

import conftest as _root_conftest
from fixtures.session_init import initialize_fresh

from titan._core import (
    ApprovedOrderIntent,
    ContractType,
    EventEnvelope,
    Instrument,
    InstrumentId,
    Money,
    OrderState,
    OrderStateMachine,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.execution import (
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    PaperConfig,
    PaperTradingEngine,
    Session,
)
from titan.research.promotion_certificate import (
    create_signed_certificate,
    execution_scope_parameters,
)

TS_NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Scripted broker stub: deterministic fault injection with broker-side truth.
# ---------------------------------------------------------------------------

class StubBroker:
    """Minimal BrokerAdapter double with inspectable broker-side order state.

    ``orders[coid]`` IS the broker's truth (raw broker vocabulary — the engine
    canonicalizes). Nothing here enforces TITAN semantics; that is exactly
    what the tests observe.
    """

    def __init__(self):
        self.orders = {}          # coid -> dict(status, filled, price, symbol, side, qty)
        self.place_calls = []     # every place_order attempt, in order
        self.place_behavior = None  # fn(intent) -> ack (may raise AFTER recording)

    # -- adapter contract ---------------------------------------------------
    def authenticate(self) -> Session:
        return Session(session_id="stub", state=AdapterSessionState.CONNECTED,
                       created_at=TS_NOW)

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(connected=True, session_state=AdapterSessionState.CONNECTED)

    def save_order_count_state(self) -> dict:
        return {}

    def restore_order_count_state(self, state: dict) -> None:
        pass

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        return BrokerPositionSnapshot(account_id=account_id, positions=[],
                                      timestamp=TS_NOW)

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        cash = Money("100000", "USD")
        return BrokerBalanceSnapshot(account_id=account_id, currency="USD", cash=cash,
                                     portfolio_value=cash, buying_power=cash,
                                     equity=cash, timestamp=TS_NOW)

    def place_order(self, intent) -> BrokerOrderAcknowledgement:
        coid = str(intent.client_order_id)
        self.place_calls.append(coid)
        if self.place_behavior is not None:
            return self.place_behavior(intent)
        self.orders[coid] = self._new_entry(intent)
        return BrokerOrderAcknowledgement(
            accepted=True, broker_order_id=BrokerOrderId(id=coid + "-broker"),
            order_status="Submitted",
        )

    def tick(self, order_id: str):
        o = self.orders.get(order_id)
        return None if o is None else self._status(order_id, o)

    def query_order(self, client_order_id: str):
        o = self.orders.get(client_order_id)
        return None if o is None else self._status(client_order_id, o)

    def cancel(self, order_id) -> CancellationAcknowledgement:
        oid = order_id.id if hasattr(order_id, "id") else str(order_id)
        if oid.endswith("-broker"):
            oid = oid[: -len("-broker")]
        if oid in self.orders:
            self.orders[oid]["status"] = "Cancelled"
        return CancellationAcknowledgement(accepted=True,
                                           broker_order_id=BrokerOrderId(id=oid))

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _new_entry(intent) -> dict:
        return {"status": "Submitted", "filled": 0, "price": None,
                "symbol": str(intent.instrument_id), "side": str(intent.side),
                "qty": int(str(intent.quantity))}

    def _status(self, oid: str, o: dict) -> BrokerOrderStatus:
        return BrokerOrderStatus(
            order_id=BrokerOrderId(id=oid),
            instrument_id=o["symbol"],
            side=o["side"],
            quantity=str(o["qty"]),
            filled_quantity=str(o["filled"]),
            price=o["price"],
            status=o["status"],
            created_at=TS_NOW,
            updated_at=TS_NOW,
        )


def broker_created(broker, intent, *, status="Submitted", filled=0, price=None):
    """Simulate the broker having created an order (e.g. response lost)."""
    entry = StubBroker._new_entry(intent)
    entry.update(status=status, filled=filled, price=price)
    broker.orders[str(intent.client_order_id)] = entry


# ---------------------------------------------------------------------------
# Engine / intent factories
# ---------------------------------------------------------------------------

def make_engine(tmp_path, adapter, instruments=("SPY",), initialize=True,
                **config_overrides):
    risk_config = RiskConfig(
        list(instruments),
        Money("100000", "USD"),
        1000,
        5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        10_000_000,
        100,
    )
    config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="test-1",
        state_path=str(tmp_path / "state.json"),
        **config_overrides,
    )
    engine = PaperTradingEngine(config, adapter)
    for instr in instruments:
        engine.register_instrument(
            Instrument(InstrumentId(instr, "PAPER"), "0.01", 1, "1.0",
                       ContractType.Stock, "USD", 2))
    if initialize:
        initialize_fresh(engine)
    return engine


def make_intent(instrument="SPY", side="BUY", quantity="1", price="450.00",
                strategy_id="recovery-strat", certificate_ref=None):
    return TradeIntent(
        strategy_id, "recovery-pkg", "test-1",
        instrument, side, quantity, "MARKET", "DAY", "1.0",
        TS_NOW, price=price,
        certificate_ref=certificate_ref or "legacy-tests-bypass-cert-gate-via-conftest",
    )


def position_qty(engine, instrument="SPY") -> int:
    pos = engine.portfolio.get_position(instrument)
    return pos.quantity if pos else 0


def open_client_ids(engine):
    return [oid for oid, sm in engine.order_states.items()
            if sm.current in (OrderState.Acknowledged, OrderState.PartiallyFilled,
                              OrderState.Submitted, OrderState.Unknown)]


# ---------------------------------------------------------------------------
# Test 1 — exactly-once fill application across submit/poller interleaving
# ---------------------------------------------------------------------------

class TestExactlyOnceFillApplication:
    def test_t1_fill_on_ack_then_poll_applies_once(self, tmp_path):
        """Ack carries the full fill; poller sees identical cumulative afterwards."""
        broker = StubBroker()

        def behavior(intent):
            broker_created(broker, intent, status="filled", filled=10, price="450.00")
            return BrokerOrderAcknowledgement(
                accepted=True, broker_order_id=BrokerOrderId(id="b-1"),
                fill_price="450.00", fill_quantity="10", order_status="filled")

        broker.place_behavior = behavior
        engine = make_engine(tmp_path, broker)
        result = engine.submit_intent(make_intent(quantity="10"))

        assert result.accepted is True
        assert len(result.fills) == 1
        assert position_qty(engine) == 10

        # Poller observes the SAME cumulative repeatedly — must be a no-op.
        for _ in range(3):
            engine.poll_fills()
        assert position_qty(engine) == 10
        assert sum(int(f.quantity) for f in result.fills) == 10

    def test_t1_fill_only_in_poller_then_late_submit_side_absorb_is_noop(self, tmp_path):
        """Reverse interleave: ack has no fill, poller absorbs, then a late
        duplicate absorption attempt applies nothing."""
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        result = engine.submit_intent(make_intent(quantity="10"))
        assert result.accepted and result.fills == []
        assert position_qty(engine) == 0

        coid = broker.place_calls[0]
        broker.orders[coid].update(status="filled", filled=10, price="450.00")
        engine.poll_fills()
        assert position_qty(engine) == 10

        sm = engine.order_states[coid]
        assert sm.current == OrderState.Filled

        # The old R1 race shape: submit-side accounting after the poller
        # already applied. Through the shared ledger this is a no-op.
        with engine._lock:
            applied = engine._absorb_broker_fill(coid, sm, 10, "450.00")
        assert applied is None
        assert position_qty(engine) == 10

    def test_t1_poller_thread_during_submissions_never_double_counts(self, tmp_path):
        """Live concurrency: background poller spinning while orders stream in."""
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        stop = threading.Event()

        def poller():
            while not stop.is_set():
                try:
                    engine.poll_fills()
                except Exception:
                    pass

        t = threading.Thread(target=poller, daemon=True)
        t.start()
        try:
            results = [engine.submit_intent(make_intent()) for _ in range(8)]
        finally:
            stop.set()
            t.join(timeout=5)

        assert all(r.accepted for r in results)
        # The stub never fills on its own: broker now reports every order
        # filled; the authoritative path must settle each exactly once.
        for coid in broker.place_calls:
            broker.orders[coid].update(status="filled", filled=1, price="450.00")
        engine.poll_fills()

        assert position_qty(engine) == 8
        assert sum(engine._order_filled_quantity.values()) == position_qty(engine)


# ---------------------------------------------------------------------------
# Test 2 — partial fill preserved through cancellation (P0 C4)
# ---------------------------------------------------------------------------

class TestPartialFillThenCancel:
    def test_t2_cancelled_with_partial_fill_preserves_position(self, tmp_path):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        result = engine.submit_intent(make_intent(quantity="100"))
        assert result.accepted
        coid = broker.place_calls[0]

        # Broker reports: partially filled, then externally cancelled (TWS UI).
        broker.orders[coid].update(status="Cancelled", filled=30, price="450.00")
        engine.poll_fills()

        assert position_qty(engine) == 30            # the 30 shares survive
        sm = engine.order_states[coid]
        assert sm.current == OrderState.Cancelled    # terminal outcome is Cancelled
        assert coid not in engine._order_metadata    # tracking dropped cleanly

        # Idempotent: repeated polls cannot resurrect or double-apply.
        for _ in range(2):
            engine.poll_fills()
        assert position_qty(engine) == 30

    def test_t2_full_cancel_zero_fill_stays_flat(self, tmp_path):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        engine.submit_intent(make_intent())
        coid = broker.place_calls[0]
        broker.orders[coid].update(status="Cancelled", filled=0)
        engine.poll_fills()
        assert position_qty(engine) == 0
        assert engine.order_states[coid].current == OrderState.Cancelled


# ---------------------------------------------------------------------------
# Test 3 — uncertain broker outcome fails safe, never resent (P0 U1)
# ---------------------------------------------------------------------------

class TestUncertainOutcome:
    def test_t3_timeout_parks_unknown_and_does_not_retry(self, tmp_path):
        broker = StubBroker()

        def lost_response(intent):
            # Broker CREATED the order; the response was lost in transit.
            broker_created(broker, intent)
            raise TimeoutError("simulated network timeout")

        broker.place_behavior = lost_response
        engine = make_engine(tmp_path, broker)

        result = engine.submit_intent(make_intent())

        assert result.accepted is False
        assert "UNKNOWN" in (result.rejection_reason or "")
        assert len(broker.place_calls) == 1                     # NEVER resent
        assert engine.risk_gate.kill_switch.blocks_routing()    # routing halted
        coid = broker.place_calls[0]
        # Resolved OPEN against broker truth: tracked, adoptable, alive.
        assert engine.order_states[coid].current == OrderState.Acknowledged
        assert open_client_ids(engine) == [coid]

    def test_t3_unknown_resolves_to_fill_exactly_once(self, tmp_path):
        broker = StubBroker()

        def lost_response(intent):
            broker_created(broker, intent, status="filled", filled=1, price="450.00")
            raise ConnectionError("response dropped")

        broker.place_behavior = lost_response
        engine = make_engine(tmp_path, broker)

        result = engine.submit_intent(make_intent())

        assert result.accepted is False
        assert len(broker.place_calls) == 1
        assert position_qty(engine) == 1             # broker truth absorbed ONCE
        coid = broker.place_calls[0]
        assert engine.order_states[coid].current == OrderState.Filled

    def test_t3_unresolvable_without_query_capability_fails_closed(self, tmp_path):
        broker = StubBroker()
        broker.place_behavior = lambda intent: (_ for _ in ()).throw(TimeoutError("x"))
        engine = make_engine(tmp_path, broker)
        engine.adapter.query_order = None   # adapter cannot answer "does it exist?"

        result = engine.submit_intent(make_intent())
        assert result.accepted is False
        coid = broker.place_calls[0]
        # Stays parked in Unknown — never declared dead, never resent.
        assert engine.order_states[coid].current == OrderState.Unknown
        assert engine.risk_gate.kill_switch.blocks_routing()


# ---------------------------------------------------------------------------
# Test 4 — reconnect gap: order invisible, then reconciled when visible again
# ---------------------------------------------------------------------------

class TestReconnectRecovery:
    def test_t4_open_order_survives_visibility_gap_and_settles(self, tmp_path):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        engine.submit_intent(make_intent(quantity="5"))
        coid = broker.place_calls[0]

        # Reconnect wipes broker-visible state (IBKR wrapper replacement).
        snapshot = broker.orders.pop(coid)
        engine.poll_fills()
        assert open_client_ids(engine) == [coid]     # NOT dropped while dark
        engine.poll_fills()

        # Visibility returns with a full fill.
        snapshot.update(status="filled", filled=5, price="450.00")
        broker.orders[coid] = snapshot
        engine.poll_fills()

        assert position_qty(engine) == 5
        assert engine.order_states[coid].current == OrderState.Filled
        engine.poll_fills()
        assert position_qty(engine) == 5


# ---------------------------------------------------------------------------
# Test 5 — concurrent submissions: one broker order each, exact accounting
# ---------------------------------------------------------------------------

class TestConcurrentSubmits:
    def test_t5_parallel_submits_produce_exact_accounting(self, tmp_path):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        n = 12
        results = [None] * n
        errors = []

        def worker(i):
            try:
                results[i] = engine.submit_intent(make_intent())
            except Exception as e:      # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors
        accepted = [r for r in results if r and r.accepted]
        assert len(broker.place_calls) == n
        assert len(set(broker.place_calls)) == n          # unique client ids
        assert len(accepted) >= 1
        total_filled = sum(int(f.quantity) for r in accepted for f in r.fills)
        assert total_filled == position_qty(engine)
        assert sum(engine._order_filled_quantity.values()) == position_qty(engine)


# ---------------------------------------------------------------------------
# Test 6 — bracket exits rejected pending OCA (P1 D2)
# ---------------------------------------------------------------------------

class _FakeIbkrWrapper:
    next_oid = 7
    _client_by_oid = {}
    _order_meta = {}
    _order_results = {}
    _order_events = {}


class _FakeIbkrClient:
    def isConnected(self):
        return True

    def serverVersion(self):
        return 1

    def __init__(self):
        self.placed = []

    def placeOrder(self, oid, contract, order):
        self.placed.append((oid, order.action, order.orderType))


def _ibkr_adapter():
    from titan.execution.ibkr_adapter import IBKRPaperAdapter
    adapter = IBKRPaperAdapter.__new__(IBKRPaperAdapter)
    adapter._connected = True
    adapter._account_id = "DU123"
    adapter._wrapper = _FakeIbkrWrapper()
    adapter._fill_timeout = 0.05
    adapter._client = _FakeIbkrClient()
    return adapter


def _approved(**overrides) -> ApprovedOrderIntent:
    kwargs = dict(
        risk_decision_id="rd", intent_id="in", client_order_id="c-x",
        instrument_id="SPY", side="BUY", quantity="1", order_type="LIMIT",
        time_in_force="DAY", risk_profile_version="1.0", price="450.00",
    )
    kwargs.update(overrides)
    return ApprovedOrderIntent(**kwargs)


class TestBracketDisabled:
    def test_t6_bracket_intent_rejected_without_placing_children(self):
        adapter = _ibkr_adapter()
        ack = adapter.place_order(_approved(client_order_id="c-bracket",
                                            stop_price="440.00",
                                            take_profit_price="470.00"))
        assert ack.accepted is False
        assert "bracket" in (ack.rejection_reason or "").lower()
        assert adapter._client.placed == []           # NOTHING reached the wire

    def test_t6_trailing_only_also_rejected(self):
        from titan._core import TrailingConfig
        adapter = _ibkr_adapter()
        ack = adapter.place_order(_approved(
            client_order_id="c-trail",
            trailing=TrailingConfig("0.002", "0.001")))
        assert ack.accepted is False
        assert adapter._client.placed == []

    def test_t6_plain_intent_places_single_parent(self):
        adapter = _ibkr_adapter()
        ack = adapter.place_order(_approved(client_order_id="c-plain"))
        assert ack.accepted is True
        assert len(adapter._client.placed) == 1       # parent only


# ---------------------------------------------------------------------------
# Test 7 — certificate binds execution scope (P0 A1)
# ---------------------------------------------------------------------------

PRIV_BYTES = b"TITAN_TEST_ED25519_KEY_32_BYTES!"   # matches tests/conftest.py pubkey env


def _scope_cert(strategy_id="recovery-strat", instrument="SPY", side="BUY",
                max_quantity=1, account="test-1", nonce=None, parameters=None):
    return create_signed_certificate(
        PRIV_BYTES, strategy_id=strategy_id, expires_at="2099-01-01T00:00:00Z",
        parameters=parameters if parameters is not None else
        execution_scope_parameters(instrument=instrument, side=side,
                                   max_quantity=max_quantity, account=account),
        nonce=nonce,
    )


def cert_json(cert) -> str:
    return json.dumps({
        "strategy_id": cert.strategy_id,
        "expires_at": cert.expires_at,
        "signature": cert.signature,
        "content_digest": cert.content_digest,
        "parameters": cert.parameters,
        "nonce": cert.nonce,
    })


class TestCertificateScope:
    @pytest.fixture
    def real_gate(self, monkeypatch):
        # conftest patches submit_intent for legacy suites; the scope gate IS
        # submit_intent, so restore the real implementation here.
        monkeypatch.setattr(PaperTradingEngine, "submit_intent",
                            _root_conftest.original_submit)

    def test_t7_valid_scope_passes(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(certificate_ref=cert_json(_scope_cert()))
        result = engine.submit_intent(intent)
        assert result.accepted is True

    def test_t7_strategy_mismatch_hard_rejects(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(
            certificate_ref=cert_json(_scope_cert(strategy_id="other-strategy")))
        with pytest.raises(ValueError, match="strategy mismatch"):
            engine.submit_intent(intent)

    def test_t7_instrument_mismatch_hard_rejects(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(
            certificate_ref=cert_json(_scope_cert(instrument="QQQ")))
        with pytest.raises(ValueError, match="instrument mismatch"):
            engine.submit_intent(intent)

    def test_t7_side_mismatch_hard_rejects(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(side="SELL",
                             certificate_ref=cert_json(_scope_cert(side="BUY")))
        with pytest.raises(ValueError, match="side mismatch"):
            engine.submit_intent(intent)

    def test_t7_quantity_over_max_hard_rejects(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(quantity="50",
                             certificate_ref=cert_json(_scope_cert(max_quantity=1)))
        with pytest.raises(ValueError, match="max_quantity"):
            engine.submit_intent(intent)

    def test_t7_account_mismatch_hard_rejects(self, tmp_path, real_gate):
        engine = make_engine(tmp_path, StubBroker())
        intent = make_intent(
            certificate_ref=cert_json(_scope_cert(account="someone-else")))
        with pytest.raises(ValueError, match="account mismatch"):
            engine.submit_intent(intent)

    def test_t7_missing_scope_parameters_hard_rejects(self, tmp_path, real_gate):
        """A legacy identity-only certificate authorizes NOTHING."""
        engine = make_engine(tmp_path, StubBroker())
        cert = create_signed_certificate(
            PRIV_BYTES, strategy_id="recovery-strat",
            expires_at="2099-01-01T00:00:00Z")     # identity only, no scope
        intent = make_intent(certificate_ref=cert_json(cert))
        with pytest.raises(ValueError, match="scope incomplete"):
            engine.submit_intent(intent)

    def test_t7_nonce_replay_hard_rejects(self, tmp_path, real_gate):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker)
        ref = cert_json(_scope_cert(nonce="nonce-xyz"))
        assert engine.submit_intent(make_intent(certificate_ref=ref)).accepted is True
        with pytest.raises(ValueError, match="nonce replayed"):
            engine.submit_intent(make_intent(certificate_ref=ref))

    def test_t7_nonce_persists_across_restart(self, tmp_path, real_gate):
        broker = StubBroker()
        engine_a = make_engine(tmp_path, broker)
        ref = cert_json(_scope_cert(nonce="nonce-persist"))
        assert engine_a.submit_intent(make_intent(certificate_ref=ref)).accepted

        engine_b = make_engine(tmp_path, broker, initialize=False)
        assert engine_b._load_state() is True   # restore durable engine state
        with pytest.raises(ValueError, match="nonce replayed"):
            engine_b.submit_intent(make_intent(certificate_ref=ref))


# ---------------------------------------------------------------------------
# Test 8 — crash after send / before acknowledgement resolves deterministically
# ---------------------------------------------------------------------------

class TestCrashRecovery:
    def _crash_after_submit_event(self, engine, broker, *, status=None, filled=0):
        """Replicate EXACTLY what submit persists before contacting the broker:
        Validated->Submitted transitions + OrderSubmitted event, then 'die'."""
        coid = "tit-crash-1"
        sm = OrderStateMachine()
        sm.transition(OrderState.Validated)
        sm.persist_transition(engine._event_store, coid, OrderState.New,
                              OrderState.Validated, "order_validated")
        sm.transition(OrderState.Submitted)
        sm.persist_transition(engine._event_store, coid, OrderState.Validated,
                              OrderState.Submitted, "order_submitted_to_broker")
        engine.order_states[coid] = sm
        engine._event_store.append(EventEnvelope(
            "OrderSubmitted", "Execution", coid, "titan_python",
            json.dumps({"client_order_id": coid, "instrument_id": "SPY",
                        "side": "BUY", "quantity": "1", "price": "450.00"})))
        engine._save_state()
        if status is not None:
            broker.orders[coid] = {"status": status, "filled": filled,
                                   "price": "450.00" if filled else None,
                                   "symbol": "SPY", "side": "BUY", "qty": 1}
        return coid

    def _restarted_engine(self, tmp_path, broker):
        """Fresh process over identical durable paths (no re-initialization:
        the Armed risk snapshot restores from the store, fail-closed)."""
        return make_engine(tmp_path, broker, initialize=False)

    def test_t8_crash_sent_but_unacked_recovers_fill_from_broker(self, tmp_path):
        broker = StubBroker()
        engine_a = make_engine(tmp_path, broker)
        coid = self._crash_after_submit_event(engine_a, broker,
                                              status="filled", filled=1)

        engine_b = self._restarted_engine(tmp_path, broker)
        engine_b.start()

        assert position_qty(engine_b) == 1             # broker fill absorbed ONCE
        assert engine_b.order_states[coid].current == OrderState.Filled
        assert coid not in broker.place_calls          # recovery never resends
        engine_b.stop()

    def test_t8_crash_never_sent_rejected_not_resent(self, tmp_path):
        broker = StubBroker()
        engine_a = make_engine(tmp_path, broker)
        coid = self._crash_after_submit_event(engine_a, broker, status=None)

        engine_b = self._restarted_engine(tmp_path, broker)
        engine_b.start()

        assert coid not in broker.place_calls          # never resent on recovery
        assert engine_b.order_states[coid].current == OrderState.Rejected
        assert not engine_b.risk_gate.kill_switch.blocks_routing()  # deterministic
        engine_b.stop()

    def test_t8_no_query_capability_fails_closed(self, tmp_path):
        broker = StubBroker()
        engine_a = make_engine(tmp_path, broker)
        self._crash_after_submit_event(engine_a, broker, status=None)

        engine_b = self._restarted_engine(tmp_path, broker)
        engine_b.adapter.query_order = None            # IBKR-shaped blindness
        engine_b.start()

        assert engine_b.risk_gate.kill_switch.blocks_routing()   # fail closed
        engine_b.stop()


# ---------------------------------------------------------------------------
# Test 9 — TWAP unavailable (P2)
# ---------------------------------------------------------------------------

class TestTwapDisabled:
    def test_t9_module_gone(self):
        with pytest.raises(ModuleNotFoundError):
            import titan.execution.twap  # noqa: F401

    def test_t9_runtime_path_rejects_before_any_artifact(self, tmp_path):
        broker = StubBroker()
        engine = make_engine(tmp_path, broker, use_twap=True)
        result = engine.submit_intent(make_intent(quantity="100"))
        assert result.accepted is False
        assert "TWAP disabled" in (result.rejection_reason or "")
        assert broker.place_calls == []
        # No durable order artifact was created for the rejected intent.
        assert all(sm.current == OrderState.New
                   for sm in engine.order_states.values()) or not engine.order_states
