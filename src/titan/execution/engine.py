import json
import math
import os
import time
import uuid
import threading
from collections import Counter, deque

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from titan._core import (
    ApprovedOrderIntent,
    ContractType,
    EventEnvelope,
    EventStore,
    Instrument,
    KillSwitchState,
    Money,
    OrderState,
    OrderStateMachine,
    PortfolioEngine,
    Position,
    ReconciliationConfig,
    ReconciliationDriftSeverity,
    ReconciliationEngine,
    ReconciliationResult,
    RiskConfig,
    RiskGate,
    RiskReasonCode,
    RiskVerdict,
    TradeIntent,
    TradingState,
)

from titan.operations.logging import StructuredLogger, LogSeverity
from titan.data.feed_health import FeedHealthVerdict
from titan.risk.release_authorization import (
    ReleaseAuthorization,
    validate as validate_release_auth,
)
from titan.risk.session_initialization import (
    SessionInitialization,
    validate as validate_initialization,
)
from titan.research.promotion_certificate import PromotionCertificateRegistry, Certificate
from titan.risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

# Terminal statuses where the broker will take no further action.
_DEAD_ORDER_STATUSES = frozenset({
    "Filled", "Rejected", "Cancelled", "Inactive", "ApiCancelled", "ApiRejected",
})
# Canonicalization: brokers report statuses in different vocabularies (TWS
# "Filled"/"PreSubmitted", Alpaca "filled"/"canceled", sim "partially_filled").
# Everything is normalized HERE so engine logic compares one vocabulary only.
_CANONICAL_STATUS_MAP = {
    "filled": "Filled",
    "partiallyfilled": "PartiallyFilled",
    "partially_filled": "PartiallyFilled",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    "rejected": "Rejected",
    "expired": "Expired",
    "apicancelled": "ApiCancelled",
    "apirejected": "ApiRejected",
    "inactive": "Inactive",
    "submitted": "Submitted",
    "pendingsubmit": "PendingSubmit",
    "presubmitted": "PreSubmitted",
    "pendingcancel": "PendingCancel",
    "pending_new": "Submitted",
    "new": "Submitted",
    "accepted": "Submitted",
    "done_for_day": "Expired",
}


def _canonical_status(status: str) -> str:
    s = (status or "").strip()
    return _CANONICAL_STATUS_MAP.get(s.lower(), s)


def _parse_qty(value) -> int:
    """Parse a broker filled-quantity ("3", "3.0", "3.5") as an integer share
    count. Unparseable values parse as 0 — never raise into the fill path."""
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0
from titan.operations._metrics_integration import (
    intents_evaluated,
    intents_rejected,
    orders_filled,
    orders_submitted,
    orders_rejected,
    kill_switch_triggered,
    trading_state_changed,
    positions_open,
    cash_balance,
    gross_exposure,
    drawdown_fraction,
)
from titan.operations._logging_integration import log_risk_decision, log_adapter_event

from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterHealth,
    BrokerFill,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    OrderResult,
    Session,
)


@dataclass
class PaperConfig:
    risk_config: RiskConfig
    reconciliation_config: Optional[ReconciliationConfig] = None
    currency: str = "USD"
    starting_capital: str = "100000"
    account_id: str = "paper-1"
    client_order_prefix: str = "tit-paper-"
    state_path: str = ".titan_state.json"
    # Authorized approver identities (init/release two-person gate). When
    # non-empty, every asserted approver must be a member (ADR-020).
    authorized_approvers: tuple[str, ...] = ()
    use_twap: bool = False
    twap_slice_count: int = 5
    twap_duration_seconds: int = 60


@dataclass
class EngineStatus:
    trading_state: TradingState
    kill_switch: KillSwitchState
    positions: list[Position]
    cash_balance: Money
    portfolio_value: Money
    open_orders: int
    adapter_health: Optional[AdapterHealth] = None
    circuit_breaker_stage: Optional[str] = None
    circuit_breaker_consecutive_errors: int = 0


class PaperTradingEngine:
    """End-to-end paper trading engine.

    Wires together: Strategy → RiskGate → Adapter → PortfolioEngine → ReconciliationEngine.
    """

    def __init__(self, config: PaperConfig, adapter: BrokerAdapter,
                 logger: Optional[StructuredLogger] = None,
                 feed_health: Optional[Callable[[], FeedHealthVerdict]] = None):
        self.config = config
        self.adapter = adapter
        self.logger = logger
        # Read-only market-data health provider for the release gate (ADR-019).
        # None => release fails closed with feed_health_absent.
        self._feed_health = feed_health
        store_path = config.state_path.replace(".json", ".db") if config.state_path else ":memory:"
        self._event_store = EventStore(store_path)
        # Fail-closed restore: missing/unreadable/deleted risk state restores
        # Triggered/Halted - a session must never silently restart trading.
        # There is NO automatic bootstrap here: a genuinely new environment
        # reaches Armed only via the explicit, audited initialize_new_session
        # command. (restore_state is fail-open and must not be used here.)
        self.risk_gate = RiskGate.load_or_default(config.risk_config, self._event_store)
        self.portfolio = PortfolioEngine(config.currency, Money(config.starting_capital, config.currency))

        recon_config = config.reconciliation_config or ReconciliationConfig()
        self.reconciler = ReconciliationEngine(recon_config)
        self.circuit_breaker = CircuitBreaker()

        self.order_states: dict[str, OrderStateMachine] = {}
        self.instruments: dict[str, Instrument] = {}
        self._session: Optional[Session] = None
        self._intent_counter: int = 0
        self._health_cache: Optional[tuple[float, bool]] = None
        self._health_cache_ttl = 5.0
        
        # Load registry for certificate verification
        pub_key = os.environ.get("TITAN_EXEC_PUBKEY", None)
        self.certificate_registry = PromotionCertificateRegistry(public_key_hex=pub_key)
        
        self._seen_init_nonces: set[str] = set()
        # Consumed certificate nonces (P0 A1): a nonce-bearing promotion
        # certificate authorizes exactly ONE accepted broker order.
        self._seen_cert_nonces: set[str] = set()
        # Reconstruct replay protection from durable events: a restart must
        # not allow a previously-used initialization nonce to be replayed
        # (nonce replay protection survives process restarts, ADR-020).
        try:
            for _ev in self._event_store.replay_by_type("SessionInitialized"):
                try:
                    _payload = json.loads(_ev.payload)
                    if _payload.get("nonce"):
                        self._seen_init_nonces.add(_payload["nonce"])
                except Exception:
                    continue
        except Exception:
            pass
        self._last_prices: dict[str, str] = {}
        self._price_history: dict[str, deque[float]] = {}
        self._order_metadata: dict[str, dict] = {}
        self._order_filled_quantity: dict[str, int] = {}
        self._decision_traces: dict[str, list[dict]] = {}
        self.intents_by_instrument: Counter = Counter()
        self.fills_by_instrument: Counter = Counter()
        self.rejections_by_instrument: Counter = Counter()
        
        self._lock = threading.RLock()
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Kill-switch release gate state (ADR-019): correlation of the current
        # trigger, nonces of already-consumed authorizations (replay protection),
        # and the durable refusal ledger (kept separate from the kill reason).
        self._kill_correlation: Optional[str] = None
        self._seen_release_nonces: set[str] = set()
        self._release_refusals: list[dict] = []


    def _restore_order_states(self) -> None:
        try:
            events = self._event_store.replay_by_type("OrderTransition")
        except Exception as e:
            if self.logger:
                self.logger.error("engine", f"Failed to replay OrderTransition events: {e}")
            return

        state_map = {
            "New": OrderState.New,
            "Validated": OrderState.Validated,
            "Submitted": OrderState.Submitted,
            "Acknowledged": OrderState.Acknowledged,
            "PartiallyFilled": OrderState.PartiallyFilled,
            "Filled": OrderState.Filled,
            "Cancelled": OrderState.Cancelled,
            "Rejected": OrderState.Rejected,
            "Expired": OrderState.Expired,
            "Unknown": OrderState.Unknown,
        }
        for ev in events:
            try:
                payload = json.loads(ev.payload)
            except Exception as e:
                if self.logger:
                    self.logger.error("engine", f"Failed to parse OrderTransition payload: {e}")
                continue
            order_id = payload.get("order_id")
            to_state_str = payload.get("to_state")
            if not order_id or not to_state_str:
                continue
            if order_id not in self.order_states:
                self.order_states[order_id] = OrderStateMachine()
            target = state_map.get(to_state_str)
            if target is not None:
                self.order_states[order_id].reset_to(target)

    def start(self, sync_from_broker: bool = False) -> Session:
        self._session = self.adapter.authenticate()
        loaded = self._replay_state_from_events() or self._load_state()
        self._restore_order_states()
        # P0 U1/T8: resolve orders persisted non-terminally by a crash — the
        # broker is queried by idempotency key; nothing is resent or guessed.
        self._recover_unresolved_orders()
        if sync_from_broker:
            self._sync_from_broker()
        self._save_state()
        if self.logger:
            self.logger.info("engine", "Session started",
                             payload={"account_id": self.config.account_id,
                                      "state_loaded": "synced" if sync_from_broker else str(loaded)})
        self._stop_event.clear()
        self._poller_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poller_thread.start()
        return self._session

    def _poll_loop(self):
        while not self._stop_event.is_set():
            try:
                self.poll_fills()
            except Exception as e:
                if self.logger:
                    self.logger.error("engine", f"Background poll failed: {e}")
            self._stop_event.wait(1.0)

    def _sync_from_broker(self) -> None:
        broker_cash = None
        broker_positions = []
        snapshot_fetch_failed = False
        try:
            bal = self.adapter.holdings(self.config.account_id)
            broker_cash = bal.cash
        except Exception as exc:
            snapshot_fetch_failed = True
            if self.logger:
                self.logger.warning("engine", f"Startup sync: holdings fetch failed: {exc}")
        try:
            pos_snap = self.adapter.positions(self.config.account_id)
            broker_positions = pos_snap.positions
        except Exception as exc:
            snapshot_fetch_failed = True
            if self.logger:
                self.logger.warning("engine", f"Startup sync: position fetch failed: {exc}")

        if snapshot_fetch_failed:
            self.trigger_kill_switch(reason="startup_broker_sync_failed")
            return

        if broker_cash is not None:
            self.portfolio = PortfolioEngine(
                self.config.currency,
                broker_cash,
            )
        for bp in broker_positions:
            qty = int(str(bp.quantity)) if bp.quantity else 0
            if qty <= 0:
                continue
            entry_price = str(bp.avg_entry_price) if hasattr(bp, 'avg_entry_price') and bp.avg_entry_price else "0"
            self.portfolio.apply_fill(
                instrument_id=str(bp.instrument_id),
                side=bp.side.lower() if hasattr(bp, 'side') else "buy",
                quantity=qty,
                price=Money(entry_price, self.config.currency),
            )

    def _replay_state_from_events(self) -> bool:
        try:
            all_events = self._event_store.replay_all()
        except Exception:
            return False
        if not all_events:
            return False
        all_events.sort(key=lambda e: e.occurred_at)

        has_position_data = False
        for ev in all_events:
            if ev.message_type in ("PositionOpened", "PositionChanged", "PositionClosed"):
                has_position_data = True
                try:
                    payload = json.loads(ev.payload)
                    instr = payload.get("instrument_id", "")
                    side = payload.get("side", "buy")
                    qty = int(payload.get("quantity", 0))
                    price = Money(str(payload.get("price", "0")), self.config.currency)
                    self.portfolio.apply_fill(instr, side, qty, price)
                except Exception:
                    continue

        for ev in all_events:
            try:
                payload = json.loads(ev.payload)
            except Exception:
                continue
            if ev.message_type == "OrderSubmitted":
                coid = payload.get("client_order_id", "")
                self._order_metadata[coid] = {
                    "instrument_id": payload.get("instrument_id", ""),
                    "side": payload.get("side", ""),
                    "quantity": int(payload.get("quantity", 0)),
                }
            elif ev.message_type == "OrderFilled":
                coid = payload.get("client_order_id", "")
                instr = payload.get("instrument_id", "")
                price = payload.get("fill_price", "")
                if coid:
                    self._order_filled_quantity[coid] = int(payload.get("filled_quantity", 0))
                if instr and price:
                    self._last_prices[instr] = price
                    try:
                        self.portfolio.update_market_price(instr, price)
                    except Exception:
                        pass

        for ev in reversed(all_events):
            if ev.message_type == "PortfolioState":
                try:
                    payload = json.loads(ev.payload)
                    self._intent_counter = payload.get("intent_counter", 0)
                    oc = payload.get("order_count")
                    if isinstance(oc, dict):
                        self.adapter.restore_order_count_state(oc)
                except Exception:
                    pass
                break

        return has_position_data

    def _build_state_dict(self) -> dict:
        return {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "portfolio": {
                "cash": {
                    "amount": self.portfolio.cash_balance.amount,
                    "currency": self.portfolio.cash_balance.currency,
                },
                "realized_pnl": {
                    "amount": self.portfolio.realized_pnl.amount,
                    "currency": self.portfolio.realized_pnl.currency,
                },
                "positions": {
                    instr: {
                        "instrument_id": pos.instrument_id,
                        "side": str(pos.side),
                        "quantity": pos.quantity,
                        "cost_basis": {
                            "amount": pos.cost_basis.amount,
                            "currency": pos.cost_basis.currency,
                        },
                    }
                    for instr, pos in self.portfolio.positions.items()
                },
            },
            "intent_counter": self._intent_counter,
            "last_prices": dict(self._last_prices),
            "order_count": self.adapter.save_order_count_state(),
            "cert_nonces": sorted(self._seen_cert_nonces),
        }

    def _append_state_snapshot(self) -> None:
        state = self._build_state_dict()
        self._event_store.append(EventEnvelope(
            "PortfolioState", "Portfolio", "system", "titan_python",
            json.dumps(state),
        ))

    def _read_latest_portfolio_snapshot(self) -> dict | None:
        try:
            events = self._event_store.replay_by_type("PortfolioState")
            if events:
                return json.loads(events[-1].payload)
        except Exception:
            pass
        return None

    def _apply_state_snapshot(self, state: dict) -> None:
        pf = state["portfolio"]
        self.portfolio = PortfolioEngine(
            pf["cash"]["currency"],
            Money(pf["cash"]["amount"], pf["cash"]["currency"]),
        )
        for instr, pos_data in pf.get("positions", {}).items():
            qty = pos_data.get("quantity", 0)
            if qty <= 0:
                continue
            side = pos_data.get("side", "")
            fill_side = "buy" if side == "Long" else "sell"
            cost = pos_data.get("cost_basis", {})
            self.portfolio.apply_fill(
                instrument_id=pos_data["instrument_id"],
                side=fill_side,
                quantity=qty,
                price=Money(cost.get("amount", "0"), cost.get("currency", pf["cash"]["currency"])),
            )

        self._intent_counter = state.get("intent_counter", 0)
        self._last_prices = {k: str(v) for k, v in state.get("last_prices", {}).items()}
        self._seen_cert_nonces = set(state.get("cert_nonces", []))
        for instr, price in self._last_prices.items():
            try:
                self.portfolio.update_market_price(instr, price)
            except Exception:
                pass

        oc = state.get("order_count")
        if oc is not None:
            if isinstance(oc, dict):
                self.adapter.restore_order_count_state(oc)
            else:
                if self.logger:
                    self.logger.error("engine", "Corrupt order_count state — halting routing")
                self.trigger_kill_switch(reason="corrupt_order_count_state")

        saved_pnl = pf.get("realized_pnl", {})
        if saved_pnl and saved_pnl["amount"] != self.portfolio.realized_pnl.amount:
            self.portfolio.set_realized_pnl(
                Money(saved_pnl["amount"], saved_pnl["currency"])
            )

    def _save_state(self, raise_on_error: bool = False) -> None:
        """Persist portfolio + risk state. Default suppresses write errors
        (best-effort for routine saves); pass raise_on_error=True from paths
        that MUST be durable (e.g. session initialization) so a failed write
        fails closed instead of silently leaving an Armed gate without its
        durable risk snapshot (ADR-020)."""
        if not self.config.state_path:
            return

        state = self._build_state_dict()
        path = Path(self.config.state_path)
        try:
            with self._lock:
                path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            if raise_on_error:
                raise

        self._append_state_snapshot()
        try:
            self.risk_gate.persist_state(self._event_store)
        except Exception:
            if raise_on_error:
                raise

    def _load_state(self) -> bool:
        if not self.config.state_path:
            return False

        path = Path(self.config.state_path)
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                self._apply_state_snapshot(state)
                return True
            except Exception:
                if self.logger:
                    self.logger.error("engine", "Corrupt state file — halting routing")
                # Fail closed, but idempotently: with strict recovery the gate is
                # ALREADY Triggered/Halted here (empty/corrupt store restored
                # fail-closed), so only trigger when routing is not yet blocked.
                self.trigger_kill_switch(reason="corrupt_portfolio_snapshot")
                return True

        snapshot = self._read_latest_portfolio_snapshot()
        if snapshot is not None:
            self._apply_state_snapshot(snapshot)
            return True

        return False


    def stop(self) -> None:
        if self._poller_thread:
            self._stop_event.set()
            self._poller_thread.join(timeout=2.0)
        self._save_state()
        try:
            self.adapter.heartbeat()
        except Exception:
            pass
        self._session = None
        if self.logger:
            self.logger.info("engine", "Session stopped")
        try:
            self._event_store.close()
        except Exception:
            pass

    def register_instrument(self, instrument: Instrument, instrument_id: str | None = None) -> None:
        key = instrument_id or instrument.instrument_id.symbol
        self.instruments[key] = instrument

    def _check_adapter_health(self, force: bool = False) -> bool:
        """Check adapter health. Returns True if healthy, False if down.

        On first failure, auto-triggers kill switch (fail-closed). Pass
        force=True to bypass the short TTL cache (used by the release gate's
        TOCTOU re-check so it reads live state, not a cached verdict).
        """
        now = time.monotonic()
        if not force and self._health_cache and (now - self._health_cache[0]) < self._health_cache_ttl:
            return self._health_cache[1]
        try:
            health = self.adapter.heartbeat()
            healthy = bool(health and health.connected)
            self._health_cache = (now, healthy)
            if healthy:
                return True
            raise ConnectionError(f"Adapter heartbeat returned disconnected: {health}")
        except Exception as e:
            self._health_cache = (now, False)
            if self.logger:
                self.logger.error("engine", f"Adapter health check failed: {e}")
            if not self.risk_gate.kill_switch.blocks_routing():
                self.trigger_kill_switch()
                if self.logger:
                    self.logger.warning("engine", "Auto-halt: kill switch triggered due to broker disconnect")
            return False

    def _trace_decision(self, correlation_id: str, stage: str, details: dict | None = None) -> None:
        if not correlation_id:
            return
        if correlation_id not in self._decision_traces:
            self._decision_traces[correlation_id] = []
        self._decision_traces[correlation_id].append(
            {"stage": stage, **(details or {})}
        )

    def update_price(self, instrument_id: str, price: str | float) -> None:
        """Update market price for an instrument and trigger portfolio M2M valuation."""
        price_str = str(price)
        self._last_prices[instrument_id] = price_str
        price_f = float(price_str)
        if instrument_id not in self._price_history:
            self._price_history[instrument_id] = deque(maxlen=60)
        self._price_history[instrument_id].append(price_f)
        try:
            self.portfolio.update_market_price(instrument_id, price_str)
        except Exception:
            pass

    def update_market_price(self, instrument_id: str, price: str | float) -> None:
        """Alias for update_price."""
        self.update_price(instrument_id, price)

    def set_feed_health(self, feed_health: Optional[Callable[[], FeedHealthVerdict]]) -> None:
        """Set or update the feed health provider callable."""
        self._feed_health = feed_health

    def _rejection_payload(self, intent: TradeIntent, reason: str) -> dict:
        return {
            "side": intent.side,
            "reason": reason,
            "mode": "paper",
            "strategy": intent.strategy_id,
            "manifest": intent.strategy_package_digest,
            "instrument": str(intent.instrument_id),
            "account": str(intent.account_id),
        }

    # ------------------------------------------------------------------
    # Authoritative fill accounting (P0 U4/R1/C4).
    #
    # Invariant, per broker order:
    #   broker cumulative filled qty
    #     -> delta = cumulative - self._order_filled_quantity[order_id]
    #     -> apply delta exactly once, under self._lock.
    #
    # There is exactly ONE application path (_absorb_broker_fill). Both the
    # submit thread and the background poller route through it; neither does
    # its own portfolio math.
    # ------------------------------------------------------------------

    def _absorb_broker_fill(
        self,
        order_id: str,
        sm: OrderStateMachine,
        cumulative_filled: int,
        fill_price: Optional[str],
        update_sm: bool = True,
    ) -> Optional[BrokerFill]:
        """Apply (cumulative_filled - already_applied) to the portfolio.

        Caller MUST hold self._lock. Returns the applied BrokerFill, or None
        when the delta is zero/non-positive or tracking metadata is absent.
        update_sm=False lets a caller absorb a fill before moving the order to
        a terminal state it computes itself (e.g. Cancelled-with-partial-fill).
        """
        meta = self._order_metadata.get(order_id)
        if meta is None:
            return None
        cumulative = _parse_qty(cumulative_filled)
        already = int(self._order_filled_quantity.get(order_id, 0))
        delta = cumulative - already
        if delta <= 0:
            return None

        instrument_id = meta["instrument_id"]
        side = str(meta["side"])
        price = str(fill_price) if fill_price not in (None, "") else (
            self._last_prices.get(instrument_id, "0"))

        old_pos = self.portfolio.get_position(instrument_id)
        old_side = str(old_pos.side) if old_pos else "None"
        old_qty = old_pos.quantity if old_pos else 0

        self.portfolio.apply_fill(
            instrument_id=instrument_id,
            side=side.lower(),
            quantity=delta,
            price=Money(price, self.config.currency),
        )
        self._last_prices[instrument_id] = price
        orders_filled.inc()
        self.fills_by_instrument[instrument_id] += 1

        new_pos = self.portfolio.get_position(instrument_id)
        if old_pos is None or old_pos.quantity == 0:
            evt_type = "PositionOpened"
        elif new_pos is not None and new_pos.quantity == 0:
            evt_type = "PositionClosed"
        else:
            evt_type = "PositionChanged"
        self._event_store.append(EventEnvelope(
            evt_type, "Portfolio", instrument_id, "titan_python",
            json.dumps({
                "instrument_id": instrument_id,
                "old_side": old_side,
                "old_quantity": old_qty,
                "side": side,
                "quantity": delta,
                "price": price,
            }),
        ))
        self._event_store.append(EventEnvelope(
            "OrderFilled", "Execution", order_id, "titan_python",
            json.dumps({
                "client_order_id": order_id,
                "instrument_id": instrument_id,
                "side": side,
                "filled_quantity": delta,
                "fill_price": price,
            }),
        ))

        # Ledger updated AFTER successful application — it IS the applied qty.
        self._order_filled_quantity[order_id] = cumulative

        if update_sm and not sm.current.is_terminal():
            total_qty = int(meta.get("quantity", 0))
            from_state = sm.current
            try:
                if total_qty > 0 and cumulative >= total_qty:
                    sm.transition(OrderState.Filled)
                    sm.persist_transition(self._event_store, order_id,
                                          from_state, OrderState.Filled, "full_fill")
                elif from_state == OrderState.Acknowledged:
                    sm.transition(OrderState.PartiallyFilled)
                    sm.persist_transition(self._event_store, order_id,
                                          from_state, OrderState.PartiallyFilled, "partial_fill")
            except ValueError as e:
                if self.logger:
                    self.logger.error("engine", f"Fill SM transition failed for {order_id}: {e}")

        return BrokerFill(
            execution_id=str(uuid.uuid4()),
            order_id=BrokerOrderId(id=order_id),
            instrument_id=instrument_id,
            side=side.upper(),
            quantity=str(delta),
            price=price,
            fees=Money("0", self.config.currency),
            currency=self.config.currency,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _resolve_unknown_order(self, order_id: str) -> bool:
        """Resolve an order in Unknown state by querying the broker by its
        idempotency key. NEVER resends. Resolution outcomes: Filled / Partial /
        Open (still working) / Cancelled / Rejected. Returns True if resolved.

        P0 U1: an uncertain broker outcome must never be treated as rejection;
        the order stays tracked until the broker's truth is known.
        """
        query = getattr(self.adapter, "query_order", None)
        if query is None:
            return False
        try:
            result = query(order_id)
        except Exception as e:
            if self.logger:
                log_adapter_event(self.logger, "unknown_resolution_error", order_id,
                                  payload={"error": str(e)})
            return False
        if result is None:
            return False
        status = _canonical_status(str(getattr(result, "status", "") or ""))
        cumulative = _parse_qty(getattr(result, "filled_quantity", 0))
        price = getattr(result, "price", None)

        with self._lock:
            sm = self.order_states.get(order_id)
            if sm is None or sm.current != OrderState.Unknown:
                return False
            dead_no_fill = status in (_DEAD_ORDER_STATUSES - {"Filled"})
            if status == "Filled" or (not dead_no_fill):
                # Working or filled: adopt into Acknowledged, then let the one
                # authoritative path apply any cumulative fill delta.
                try:
                    sm.transition(OrderState.Acknowledged)
                    sm.persist_transition(self._event_store, order_id,
                                          OrderState.Unknown, OrderState.Acknowledged,
                                          "broker_outcome_resolved")
                except ValueError:
                    return False
                self._absorb_broker_fill(order_id, sm, cumulative, price)
                return True
            # Dead without further fills possible (Cancelled/Rejected/...):
            # preserve any partial fill FIRST, then take the terminal state.
            self._absorb_broker_fill(order_id, sm, cumulative, price, update_sm=False)
            target = OrderState.Cancelled if status == "Cancelled" else OrderState.Rejected
            from_state = sm.current
            try:
                sm.transition(target)
                sm.persist_transition(self._event_store, order_id, from_state, target,
                                      f"broker_outcome_{status.lower()}")
            except ValueError as e:
                if self.logger:
                    self.logger.error("engine", f"Unknown-resolution transition failed for {order_id}: {e}")
                return False
            self._order_metadata.pop(order_id, None)
            self._order_filled_quantity.pop(order_id, None)
        if self.logger:
            log_adapter_event(self.logger, "unknown_resolved", order_id,
                              payload={"status": status, "filled": cumulative})
        return True

    def _recover_unresolved_orders(self) -> None:
        """Startup crash recovery for non-terminal persisted orders.

        New/Validated: the send path persists these strictly BEFORE contacting
        the broker, so they were never sent — reject locally (deterministic).

        Submitted: ambiguous (crash between persist and send, or lost broker
        response). Query the broker by idempotency key: found -> adopt into
        Unknown and resolve; definitively not found -> rejected locally; query
        capability absent -> FAIL CLOSED (kill switch), never guess.
        """
        with self._lock:
            unresolved = [(oid, sm.current) for oid, sm in self.order_states.items()
                          if sm.current in (OrderState.New, OrderState.Validated,
                                            OrderState.Submitted)]
        query = getattr(self.adapter, "query_order", None)
        unresolvable = False
        for oid, from_current in unresolved:
            if from_current in (OrderState.New, OrderState.Validated):
                with self._lock:
                    sm = self.order_states.get(oid)
                    if sm is None or sm.current != from_current:
                        continue
                    try:
                        sm.transition(OrderState.Rejected)
                        sm.persist_transition(self._event_store, oid, from_current,
                                              OrderState.Rejected, "never_submitted_to_broker")
                    except ValueError:
                        continue
                continue
            # Submitted at startup: resolve against broker truth.
            if query is None:
                # Adapter cannot answer "does this order exist?" (e.g. IBKR).
                # Never guess — fail closed.
                unresolvable = True
                continue
            try:
                found = query(oid)
            except Exception:
                found = None
            adopted = False
            with self._lock:
                sm = self.order_states.get(oid)
                if sm is None or sm.current != from_current:
                    continue
                if found is not None:
                    if oid not in self._order_metadata:
                        self._order_metadata[oid] = {
                            "instrument_id": getattr(found, "instrument_id", "") or "",
                            "side": getattr(found, "side", "") or "",
                            "quantity": int(str(getattr(found, "quantity", "0") or "0") or 0),
                        }
                        self._order_filled_quantity.setdefault(oid, 0)
                    try:
                        sm.transition(OrderState.Unknown)
                        sm.persist_transition(self._event_store, oid, from_current,
                                              OrderState.Unknown, "startup_outcome_unknown")
                        adopted = True
                    except ValueError:
                        continue
            if adopted:
                self._resolve_unknown_order(oid)
            else:
                with self._lock:
                    sm2 = self.order_states.get(oid)
                    if sm2 is not None and sm2.current == OrderState.Submitted:
                        try:
                            sm2.transition(OrderState.Rejected)
                            sm2.persist_transition(self._event_store, oid,
                                                   OrderState.Submitted, OrderState.Rejected,
                                                   "not_found_at_broker")
                        except ValueError:
                            pass
        if unresolvable:
            if self.logger:
                self.logger.warning("engine",
                                    "Startup recovery: unresolved Submitted orders with no "
                                    "broker query capability — failing closed")
            self.trigger_kill_switch(reason="unresolved_orders_at_startup")

    def submit_intent(self, intent: TradeIntent, *, correlation_id: str = "") -> OrderResult:
        if getattr(intent, "producer_kind", "") == "shadow" or "shadow" in str(getattr(intent, "strategy_id", "")).lower():
            raise ValueError("Shadow intents are strictly forbidden in the execution engine.")
            
        cert_json = getattr(intent, "certificate_ref", None)
        if not cert_json:
            raise ValueError("Missing execution certificate (certificate_ref is None). Unauthorized intent.")

        try:
            cert_data = json.loads(cert_json)
            cert = Certificate(**cert_data)
            self.certificate_registry.verify(cert)
        except Exception as e:
            raise ValueError(f"Execution certificate verification failed: {str(e)}")

        # P0 A1: a promotion certificate authorizes a bounded execution SCOPE,
        # not merely a strategy identity. The signature already covers
        # strategy_id/expiry/digest/parameters; here we bind the actual intent
        # to that scope. Any mismatch is a hard rejection.
        if str(cert.strategy_id) != str(intent.strategy_id):
            raise ValueError(
                f"Certificate scope violation: strategy mismatch "
                f"(cert={cert.strategy_id}, intent={intent.strategy_id})")
        scope = cert.parameters or {}
        missing = [k for k in ("instrument", "side", "max_quantity", "account")
                   if k not in scope]
        if missing:
            raise ValueError(
                f"Certificate scope incomplete (missing: {missing}) — unauthorized intent")
        if str(intent.instrument_id) != str(scope["instrument"]):
            raise ValueError(
                f"Certificate scope violation: instrument mismatch "
                f"(cert={scope['instrument']}, intent={intent.instrument_id})")
        allowed_side = str(scope["side"]).upper()
        intent_side = str(intent.side).upper()
        if allowed_side not in ("BOTH", "ANY") and intent_side != allowed_side:
            raise ValueError(
                f"Certificate scope violation: side mismatch "
                f"(cert={allowed_side}, intent={intent_side})")
        try:
            if int(str(intent.quantity)) > int(str(scope["max_quantity"])):
                raise ValueError(
                    f"Certificate scope violation: quantity {intent.quantity} exceeds "
                    f"max_quantity {scope['max_quantity']}")
        except (TypeError, ValueError) as e:
            if "scope violation" in str(e):
                raise
            raise ValueError(
                f"Certificate scope invalid: max_quantity={scope['max_quantity']!r}") from e
        if str(intent.account_id) != str(scope["account"]):
            raise ValueError(
                f"Certificate scope violation: account mismatch "
                f"(cert={scope['account']}, intent={intent.account_id})")
        if "order_types" in scope:
            allowed_types = [str(t).upper() for t in scope["order_types"]]
            if str(intent.order_type).upper() not in allowed_types:
                raise ValueError(
                    f"Certificate scope violation: order_type "
                    f"{intent.order_type} not in {allowed_types}")
        if getattr(cert, "nonce", None):
            if cert.nonce in self._seen_cert_nonces:
                raise ValueError("Certificate nonce replayed — unauthorized intent")

        return self._submit_intent_core(intent, correlation_id=correlation_id,
                                        cert_nonce=getattr(cert, "nonce", None))

    def _submit_intent_core(self, intent: TradeIntent, *, correlation_id: str = "",
                            cert_nonce: Optional[str] = None) -> OrderResult:
        instr_str = str(intent.instrument_id)
        self.intents_by_instrument[instr_str] += 1

        with self._lock:
            if not self._check_adapter_health():
                self.rejections_by_instrument[instr_str] += 1
                payload = self._rejection_payload(intent, "ADAPTER_UNHEALTHY")
                if self.logger:
                    self.logger.warning("engine", f"{intent.side} rejected — routing prevented",
                                        correlation_id=correlation_id, payload=payload)
                return OrderResult(accepted=False, rejection_reason=f"Adapter unhealthy — trading halted")

        if not TradingState.Active.accepts_intents():
            self.rejections_by_instrument[instr_str] += 1
            payload = self._rejection_payload(intent, "TRADING_HALTED")
            if self.logger:
                self.logger.warning("engine", f"{intent.side} rejected — routing prevented",
                                    correlation_id=correlation_id, payload=payload)
            return OrderResult(accepted=False, rejection_reason="Trading state is not active")

        if self.risk_gate.kill_switch.blocks_routing():
            self.rejections_by_instrument[instr_str] += 1
            payload = self._rejection_payload(intent, "SAFETY_KILL_SWITCH")
            if self.logger:
                self.logger.warning("engine", f"{intent.side} rejected — routing prevented",
                                    correlation_id=correlation_id, payload=payload)
            return OrderResult(accepted=False, rejection_reason="Kill switch is blocking routing")

        instr_id = str(intent.instrument_id)
        instrument = self.instruments.get(instr_id)
        if instrument is None:
            self.rejections_by_instrument[instr_str] += 1
            return OrderResult(accepted=False, rejection_reason=f"Instrument is not registered: {instr_id}")
        raw = instrument.validate_order(intent.side or "BUY", int(intent.quantity), intent.price or "0")
        if raw is not None:
            self.rejections_by_instrument[instr_str] += 1
            if self.logger:
                self.logger.warning("engine", f"Intent rejected: instrument validation: {raw}")
            return OrderResult(accepted=False, rejection_reason=f"Instrument validation failed: {raw}")

        intents_evaluated.inc()

        # Circuit breaker: rate-limit and consecutive-error trip gate.
        # Checked AFTER instrument validation (so we don't count malformed
        # intents against the rate limit) and BEFORE the Rust RiskGate
        # (so a tripped breaker prevents all downstream evaluation).
        cb_ok, cb_reason = self.circuit_breaker.record_intent()
        if not cb_ok:
            self.rejections_by_instrument[instr_str] += 1
            intents_rejected.inc()
            if self.logger:
                self.logger.warning("engine", f"{intent.side} rejected — circuit breaker: {cb_reason}",
                                    correlation_id=correlation_id)
            return OrderResult(accepted=False, rejection_reason=f"Circuit breaker: {cb_reason}")

        for instr, price in self._last_prices.items():
            try:
                self.portfolio.update_market_price(instr, price)
            except Exception:
                pass

        snapshot = self.portfolio.get_snapshot()
        pos = self.portfolio.get_position(str(intent.instrument_id))
        pos_side = str(pos.side) if pos is not None else None

        # Correlation check — compute pairwise Pearson r with held positions
        correlation_scores = None
        cand_prices = self._price_history.get(str(intent.instrument_id))
        if cand_prices and len(cand_prices) >= 10:
            scores = []
            for held_id in self.portfolio.positions:
                held_prices = self._price_history.get(held_id)
                if held_prices and len(held_prices) >= 10:
                    r = _pearson_correlation(list(cand_prices), list(held_prices))
                    if r is not None:
                        scores.append(r)
            if scores:
                correlation_scores = scores

        verdict = self.risk_gate.evaluate(
            intent,
            self._current_position_size(intent.instrument_id),
            self._current_gross_exposure(),
            snapshot.drawdown_fraction,
            snapshot.daily_realized_loss,
            pos_side,
            correlation_scores,
        )

        if not verdict.accepted:
            self.rejections_by_instrument[instr_str] += 1
            reason = verdict.reason_detail or str(verdict.reason)
            self._trace_decision(correlation_id, "RiskDecision",
                                 {"accepted": False, "reason": reason})
            intents_rejected.inc()
            if self.logger:
                log_risk_decision(self.logger, str(intent.instrument_id), False, reason,
                                  instrument_id=str(intent.instrument_id))
            return OrderResult(accepted=False, rejection_reason=reason)

        self._trace_decision(correlation_id, "RiskDecision",
                             {"accepted": True})

        # P2 (architecture freeze): TWAP is DISABLED. The slice executor called
        # the adapter directly — bypassing risk gating, event ordering, and fill
        # accounting — and imported a nonexistent module. It stays unavailable
        # until reimplemented ON the engine pipeline. Rejected BEFORE any
        # durable order artifact is created.
        if self.config.use_twap:
            self.rejections_by_instrument[instr_str] += 1
            intents_rejected.inc()
            return OrderResult(
                accepted=False,
                rejection_reason="TWAP disabled (execution-integrity freeze)",
            )

        self._intent_counter += 1
        ts = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
        client_order_id = f"{self.config.client_order_prefix}{ts}-{self._intent_counter}"

        approved = ApprovedOrderIntent(
            risk_decision_id=str(uuid.uuid4()),
            intent_id=str(uuid.uuid4()),
            client_order_id=client_order_id,
            instrument_id=str(intent.instrument_id),
            side=str(intent.side),
            quantity=str(intent.quantity),
            order_type=str(intent.order_type),
            time_in_force=str(intent.time_in_force),
            risk_profile_version="1.0",
            price=str(intent.price) if intent.price else None,
            stop_price=str(intent.stop_price) if hasattr(intent, 'stop_price') and intent.stop_price else None,
            take_profit_price=str(intent.take_profit_price) if hasattr(intent, 'take_profit_price') and intent.take_profit_price else None,
            trailing=intent.trailing if hasattr(intent, 'trailing') else None,
        )

        secret_key = getattr(self.config, 'risk_secret_key', 'TITAN_RISK_SECRET_KEY')
        if hasattr(approved, 'attach_risk_token'):
            approved.attach_risk_token(secret_key)

        # Fail closed verification
        if hasattr(approved, 'verify_risk_token') and not approved.verify_risk_token(secret_key):
            self.rejections_by_instrument[instr_str] += 1
            intents_rejected.inc()
            return OrderResult(accepted=False, rejection_reason="Unsigned or invalid risk token")

        self._trace_decision(correlation_id, "ApprovedOrderIntent",
                             {"client_order_id": client_order_id,
                              "risk_decision_id": approved.risk_decision_id,
                              "instrument_id": str(intent.instrument_id)})

        sm = OrderStateMachine()
        sm.transition(OrderState.Validated)
        sm.persist_transition(self._event_store, client_order_id, OrderState.New, OrderState.Validated, "order_validated")
        sm.transition(OrderState.Submitted)
        sm.persist_transition(self._event_store, client_order_id, OrderState.Validated, OrderState.Submitted, "order_submitted_to_broker")
        self.order_states[client_order_id] = sm

        self._event_store.append(EventEnvelope(
            "OrderSubmitted", "Execution", client_order_id, "titan_python",
            json.dumps({
                "client_order_id": client_order_id,
                "instrument_id": str(intent.instrument_id),
                "side": str(intent.side),
                "quantity": str(intent.quantity),
                "price": str(intent.price) if intent.price else "0",
            }),
        ))

        orders_submitted.inc()

        try:
            acknowledgement = self.adapter.place_order(approved)
        except Exception as e:
            # P0 U1: a broker exception means the outcome is UNKNOWN — the
            # request may have failed before the broker saw it, OR the broker
            # may have created the order and lost the response. We must NOT
            # declare it Rejected (it may be live) and must NOT resend.
            # Fail safe: park the order in Unknown (tracked, resolvable),
            # halt routing, and resolve against broker truth by idempotency key.
            orders_rejected.inc()
            self.circuit_breaker.record_error(str(e))
            with self._lock:
                try:
                    sm.transition(OrderState.Unknown)
                    sm.persist_transition(self._event_store, client_order_id,
                                          OrderState.Submitted, OrderState.Unknown,
                                          f"broker_error_unknown_outcome: {e}")
                    self._order_metadata[client_order_id] = {
                        "instrument_id": str(intent.instrument_id),
                        "side": str(intent.side),
                        "quantity": int(str(approved.quantity)),
                    }
                    self._order_filled_quantity.setdefault(client_order_id, 0)
                except ValueError:
                    pass
            if self.logger:
                self.logger.error("engine",
                                  f"Broker submit outcome UNKNOWN (order parked, not resent): {e}")
            if not self.risk_gate.kill_switch.blocks_routing():
                self.trigger_kill_switch(reason="broker_outcome_unknown")
            self._resolve_unknown_order(client_order_id)
            return OrderResult(
                accepted=False,
                rejection_reason=f"Broker outcome UNKNOWN (order parked, not resent): {e}",
            )
        if not acknowledgement.accepted:
            self.rejections_by_instrument[instr_str] += 1
            sm.transition(OrderState.Rejected)
            sm.persist_transition(self._event_store, client_order_id, OrderState.Submitted, OrderState.Rejected, f"broker_rejected: {acknowledgement.rejection_reason}")
            orders_rejected.inc()
            if self.logger:
                log_adapter_event(self.logger, "rejected", client_order_id,
                                  instrument_id=str(intent.instrument_id),
                                  payload={"reason": acknowledgement.rejection_reason})
            return OrderResult(
                accepted=False,
                rejection_reason=acknowledgement.rejection_reason,
            )

        broker_id = acknowledgement.broker_order_id
        self.circuit_breaker.record_success()
        fills: list[BrokerFill] = []
        with self._lock:
            sm.transition(OrderState.Acknowledged)
            sm.persist_transition(self._event_store, client_order_id, OrderState.Submitted, OrderState.Acknowledged, "order_acknowledged_by_broker")
            self._event_store.append(EventEnvelope(
                "OrderAcknowledged", "Execution", client_order_id, "titan_python",
                json.dumps({
                    "client_order_id": client_order_id,
                    "broker_order_id": str(broker_id.id) if broker_id else "",
                    "instrument_id": str(intent.instrument_id),
                }),
            ))
            self._trace_decision(correlation_id, "BrokerAcknowledgement",
                                 {"broker_order_id": str(broker_id.id) if broker_id else None,
                                  "client_order_id": client_order_id,
                                  "accepted": True})

            # Register poll tracking UNDER THE LOCK before any fill absorption.
            # The poller can therefore never observe an Acknowledged order that
            # lacks its ledger entry — this closes the old R1 double-apply race.
            self._order_metadata[client_order_id] = {
                "instrument_id": str(intent.instrument_id),
                "side": str(intent.side),
                "quantity": int(str(approved.quantity)),
            }
            self._order_filled_quantity.setdefault(client_order_id, 0)

            # P0 U4/R1: single authoritative fill-application path. Any fill
            # already present on the acknowledgement goes through the SAME
            # locked delta function the poller uses — never separate math.
            if acknowledgement.fill_quantity:
                applied = self._absorb_broker_fill(
                    client_order_id, sm,
                    acknowledgement.fill_quantity,
                    acknowledgement.fill_price or approved.price)
                if applied is not None:
                    fills.append(applied)

        # Consume the certificate nonce ONLY on a broker-accepted order.
        if cert_nonce:
            self._seen_cert_nonces.add(cert_nonce)

        self._save_state()
        if self.logger:
            log_adapter_event(self.logger,
                              "filled" if fills else "order_working",
                              client_order_id,
                              instrument_id=str(intent.instrument_id),
                              payload={"fills": len(fills),
                                       "qty": str(intent.quantity)})

        position = self.portfolio.get_position(str(intent.instrument_id))
        cash = self.portfolio.get_cash_balance()
        return OrderResult(
            accepted=True,
            broker_order_id=broker_id,
            fills=fills,
            position=position,
            cash_balance=cash,
        )

    def poll_fills(self) -> None:
        """Check all open orders (Acknowledged/PartiallyFilled/Unknown) against
        the adapter and absorb broker truth. Runs on the background poller and
        can also be invoked synchronously; all state changes go through the
        single authoritative absorption path under self._lock.
        """
        with self._lock:
            open_orders = [(oid, sm.current) for oid, sm in self.order_states.items()
                           if sm.current in (OrderState.Acknowledged,
                                             OrderState.PartiallyFilled,
                                             OrderState.Unknown)]

        for order_id, from_current in open_orders:
            if from_current == OrderState.Unknown:
                # Uncertain outcome: resolve by querying the broker — never
                # guess, never resend (P0 U1).
                try:
                    self._resolve_unknown_order(order_id)
                except Exception as e:
                    log_adapter_event(self.logger, "unknown_resolution_warning",
                                      order_id, payload={"error": str(e)})
                continue

            with self._lock:
                sm = self.order_states.get(order_id)
                if sm is None or sm.current != from_current:
                    continue
                meta = self._order_metadata.get(order_id)
                already_filled = self._order_filled_quantity.get(order_id, 0)
            if meta is None:
                continue

            try:
                result = self.adapter.tick(order_id)
            except AttributeError as e:
                log_adapter_event(self.logger, "fill_poll_error", order_id, payload={"error": f"Adapter missing tick method: {e}"})
                continue
            except Exception as e:
                log_adapter_event(self.logger, "fill_poll_warning", order_id, payload={"error": str(e)})
                continue
            if result is None:
                continue

            status = _canonical_status(str(getattr(result, "status", "") or ""))
            cumulative = _parse_qty(getattr(result, "filled_quantity", 0))
            price = getattr(result, "price", None)

            dead_no_fill = status in (_DEAD_ORDER_STATUSES - {"Filled"})

            with self._lock:
                sm = self.order_states.get(order_id)
                if sm is None or sm.current != from_current or \
                        self._order_metadata.get(order_id) != meta:
                    continue

                if dead_no_fill:
                    # P0 C4: cancellation/rejection is an order-state outcome,
                    # NOT proof that zero shares filled. Absorb any fill delta
                    # BEFORE taking the terminal state, then drop tracking.
                    if cumulative > already_filled:
                        self._absorb_broker_fill(order_id, sm, cumulative, price,
                                                 update_sm=False)
                    target = (OrderState.Cancelled if status == "Cancelled"
                              else OrderState.Rejected)
                    try:
                        sm.transition(target)
                        sm.persist_transition(self._event_store, order_id, from_current,
                                              target, f"broker_{status.lower()}")
                    except ValueError as e:
                        if self.logger:
                            self.logger.error("engine",
                                              f"Dead-order transition failed for {order_id}: {e}")
                    self._order_metadata.pop(order_id, None)
                    self._order_filled_quantity.pop(order_id, None)
                    log_adapter_event(self.logger, "broker_dead_order", order_id,
                                      payload={"status": status,
                                               "instrument_id": result.instrument_id,
                                               "absorbed_qty": cumulative})
                    continue

                if status not in ("Filled", ""):
                    # Still working at the broker — nothing to do this poll.
                    continue

                # Filled (fully or partially): one authoritative delta path.
                self._absorb_broker_fill(order_id, sm, cumulative, price)

    def reconcile(self) -> ReconciliationResult:
        with self._lock:
            broker_positions = []
            positions_unavailable = False
            try:
                pos_snapshot = self.adapter.positions(self.config.account_id)
                broker_positions = pos_snapshot.positions
            except Exception as e:
                # One retry: transient API hiccups (TWS overload, reconnect window)
                # must not halt a healthy session. A second failure fails closed —
                # the compare below will flag the empty set and trip the kill switch
                # with a clear reason in the log.
                if self.logger:
                    self.logger.warning("engine", f"Reconcile: position fetch failed ({e}); retrying once")
                time.sleep(1.0)
                try:
                    pos_snapshot = self.adapter.positions(self.config.account_id)
                    broker_positions = pos_snapshot.positions
                except Exception as e2:
                    # Two consecutive failures: likely the TWS "API wedge"
                    # (account queries stall while market data flows). Force a
                    # fresh connection and try once more before failing closed.
                    if self.logger:
                        self.logger.warning("engine", f"Reconcile: position fetch failed after retry ({e2}); forcing reconnect")
                    if hasattr(self.adapter, "ensure_connected"):
                        try:
                            self.adapter.ensure_connected(force=True)
                        except Exception:
                            pass
                    try:
                        pos_snapshot = self.adapter.positions(self.config.account_id)
                        broker_positions = pos_snapshot.positions
                    except Exception as e3:
                        positions_unavailable = True
                        if self.logger:
                            self.logger.warning("engine", f"Reconcile: position fetch failed after reconnect: {e3}")

            broker_cash = None
            try:
                bal_snapshot = self.adapter.holdings(self.config.account_id)
                broker_cash = bal_snapshot.cash
            except Exception as e:
                if self.logger:
                    self.logger.warning("engine", f"Reconcile: holdings fetch failed: {e}")
            if broker_cash is None:
                # Broker cash unavailable — skip cash verification rather than
                # comparing against a zero balance (which would read as a 100%
                # phantom cash drift and trip the kill switch on a hiccup).
                broker_cash = self.portfolio.get_cash_balance()
                if self.logger:
                    self.logger.warning("engine", "Reconcile: cash verification skipped (broker cash unavailable)")

            result = self.reconciler.compare(
                self.portfolio,
                broker_positions,
                broker_cash,
            )
            if result.severity is not None and result.severity == ReconciliationDriftSeverity.Critical:
                if self.logger:
                    from titan.operations._logging_integration import log_reconciliation
                    log_reconciliation(self.logger, {"has_drift": len(result.position_drifts) > 0,
                                                      "drift_count": len(result.position_drifts),
                                                      "severity": str(result.severity),
                                                      "action": "trigger_kill_switch"})
                self.trigger_kill_switch(reason="release_re_trigger_causal_condition")
                self._save_state()
            elif self.logger:
                from titan.operations._logging_integration import log_reconciliation
                drift_count = len(result.position_drifts)
                log_reconciliation(self.logger, {"has_drift": drift_count > 0,
                                                  "drift_count": drift_count,
                                                  "severity": str(result.severity)})
            return result

    def status(self) -> EngineStatus:
        with self._lock:
            positions = []
            for instr in self.config.risk_config.instrument_eligibility:
                pos = self.portfolio.get_position(instr)
                if pos is not None:
                    positions.append(pos)

            cash = self.portfolio.get_cash_balance()
            pv = self._calculate_portfolio_value(positions, cash)
            open_count = len(self.order_states)

            positions_open.set(float(len(positions)))
            cash_balance.set(float(cash.amount))
            gross_exposure.set(float(self.portfolio.total_gross_exposure().amount))
            drawdown_fraction.set(self.portfolio.drawdown_fraction())

            health = None
            try:
                health = self.adapter.heartbeat()
            except Exception:
                pass

            cb_status = self.circuit_breaker.get_status()
            return EngineStatus(
                trading_state=self.risk_gate.trading_state,
                kill_switch=self.risk_gate.kill_switch,
                positions=positions,
                cash_balance=cash,
                portfolio_value=pv,
                open_orders=open_count,
                adapter_health=health,
                circuit_breaker_stage=cb_status.stage.value,
                circuit_breaker_consecutive_errors=cb_status.consecutive_errors,
            )

    def get_per_instrument_stats(self) -> dict[str, dict]:
        with self._lock:
            stats = {}
            all_instruments = (
                set(self.intents_by_instrument.keys())
                | set(self.fills_by_instrument.keys())
                | set(self.rejections_by_instrument.keys())
                | set(self.instruments.keys())
            )
            for instr in sorted(all_instruments):
                pos = self.portfolio.get_position(instr)
                stats[instr] = {
                    "intents": self.intents_by_instrument[instr],
                    "fills": self.fills_by_instrument[instr],
                    "rejections": self.rejections_by_instrument[instr],
                    "position": pos.quantity if pos else 0,
                    "side": str(pos.side) if pos else "NONE",
                    "price": self._last_prices.get(instr, "0.00"),
                }
            return stats

    def trigger_kill_switch(self, reason: str = "operator_or_system_trigger") -> None:
        if self._kill_correlation is None:
            self._kill_correlation = f"ks-{uuid.uuid4().hex[:12]}"
        if not self.risk_gate.kill_switch.is_triggered():
            self.risk_gate.trigger_kill_switch()
            # Durable audit event: recorded ONLY on a real transition, so a
            # held/restored gate (fail-closed) never mints spurious triggers.
            try:
                self._event_store.append(EventEnvelope(
                    "KillSwitchTriggered", "RiskControl", self._kill_correlation,
                    "titan_python",
                    json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "reason": reason,
                        "correlation_id": self._kill_correlation,
                    }),
                ))
            except Exception as e:
                if self.logger:
                    self.logger.error("engine", f"KillSwitchTriggered append failed: {e}")
        # Snapshot save is best-effort here: the durable event is already
        # appended above, and a save failure must not mask the trigger outcome
        # (e.g. the init-persistence-failure path re-raises its own error).
        try:
            self._save_state()
        except Exception as e:
            if self.logger:
                self.logger.error("engine", f"KillSwitchTriggered state save failed: {e}")
        kill_switch_triggered.inc()
        if self.logger:
            self.logger.warning("engine", f"Kill switch triggered: reason={reason}")


    def _record_init_refusal(self, reason: str) -> None:
        """Durable audit record for a refused initialization.

        Durability is mandatory (ADR-020): if the refusal event cannot be
        persisted, fail loudly instead of silently dropping the audit trail.
        """
        try:
            self._event_store.append(EventEnvelope(
                "InitializationRefused", "SessionInitialization", "system",
                "titan_python",
                json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                            "reason": reason}),
            ))
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "engine",
                    f"InitializationRefused NOT persisted (reason={reason}): {e}")
            raise RuntimeError(
                "initialization refusal not durably recorded "
                f"(reason={reason}): {e}") from e
        if self.logger:
            self.logger.warning("engine", f"Session initialization refused: {reason}")

    def initialize_new_session(self,
                               initialization: Optional[SessionInitialization] = None) -> None:
        """Explicit, operator-controlled initialization of a NEW session.

        Distinct from ordinary startup and NEVER triggered by an empty store.
        Same authorization discipline as release: missing / incomplete /
        expired / replayed initialization refuses, durably recorded. Refuses
        when risk state already exists (initialization must not be usable to
        bypass the release discipline on an existing session). On success the
        gate is armed (Triggered/Halted -> Armed/Active) and an Armed risk
        snapshot is persisted so later restarts restore Armed.
        """
        # One locked transaction: validation, existing-state detection, the
        # durable audit event, the state transition, and the nonce commit are
        # all serialized so two concurrent callers cannot double-initialize.
        with self._lock:
            reason = validate_initialization(
                initialization, self._seen_init_nonces,
                authorized_approvers=self.config.authorized_approvers,
            )
            if reason:
                self._record_init_refusal(reason)
                raise RuntimeError(f"Cannot initialize session: kill_reason={reason}")
            if self._event_store.replay_by_type("RiskStateSnapshot"):
                self._record_init_refusal("initialization_conflicts_with_existing_state")
                raise RuntimeError(
                    "Cannot initialize session: kill_reason="
                    "initialization_conflicts_with_existing_state")

            # Durable audit FIRST: never arm a gate without its audit trail.
            # If the audit event cannot be persisted, refuse while the gate
            # is still fail-closed held and no nonce has been consumed.
            try:
                self._event_store.append(EventEnvelope(
                    "SessionInitialized", "SessionInitialization", "system",
                    "titan_python",
                    json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "approvers": [a.approver for a in initialization.approvers],
                        "rationale": initialization.rationale,
                        "nonce": initialization.nonce,
                    }),
                ))
            except Exception as e:
                if self.logger:
                    self.logger.error("engine", f"SessionInitialized append failed: {e}")
                raise RuntimeError(
                    f"Cannot initialize session: kill_reason="
                    f"initialization_audit_write_failed ({e})") from e

            # Arm, then persist the Armed snapshot. On persistence failure,
            # restore the held state so an Armed in-memory gate can never
            # outlive a failed initialization.
            self.risk_gate._initialize_armed()
            try:
                self._save_state(raise_on_error=True)
            except Exception as e:
                self.trigger_kill_switch(reason="initialization_persistence_failed")
                raise RuntimeError(
                    f"Cannot initialize session: kill_reason="
                    f"initialization_persistence_failed ({e})") from e

            # Nonce committed LAST — only a fully-durable init consumes it.
            self._seen_init_nonces.add(initialization.nonce)
            if self.logger:
                self.logger.info("engine", "Session initialized (explicit, audited)")

    def _evaluate_feed_health(self) -> FeedHealthVerdict:
        """Fail-closed feed-health verdict. No provider => feed_health_absent."""
        if self._feed_health is None:
            return FeedHealthVerdict(False, "feed_health_absent", {},
                                     datetime.now(timezone.utc).isoformat())
        try:
            verdict = self._feed_health()
        except Exception:
            return FeedHealthVerdict(False, "feed_health_error", {},
                                     datetime.now(timezone.utc).isoformat())
        return verdict if verdict is not None else FeedHealthVerdict(
            False, "feed_health_error", {}, datetime.now(timezone.utc).isoformat())

    def _record_release_refusal(self, reason: str, details: Optional[dict] = None) -> None:
        """Durable release-refusal audit entry, kept separate from the kill reason."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "correlation": self._kill_correlation,
            "reason": reason,
            "details": details or {},
        }
        self._release_refusals.append(entry)
        try:
            self._event_store.append(EventEnvelope(
                "ReleaseRefusal", "KillSwitchRelease", "system", "titan_python",
                json.dumps(entry),
            ))
        except Exception:
            pass
        if self.logger:
            self.logger.warning("engine", f"Kill switch release refused: {reason}")

    def _require_release_authorization(
        self, authorization: Optional[ReleaseAuthorization]
    ) -> None:
        """Enforce the RISK_POLICY release authority model (ADR-019)."""
        code = validate_release_auth(
            authorization,
            self._kill_correlation,
            seen_nonces=self._seen_release_nonces,
        )
        if code:
            self._record_release_refusal(code)
            raise RuntimeError(f"Cannot release kill switch: kill_reason={code}")
        # NOTE: the nonce is NOT consumed here. It is marked seen only on a
        # successful release commit, so a refusal (transient feed/adapter/
        # reconcile hiccup) does not burn a still-valid authorization record.

    def release_kill_switch(
        self, authorization: Optional[ReleaseAuthorization] = None
    ) -> None:
        """Release the kill switch under the ADR-019 / RISK_POLICY gate.

        Sequence: not-held no-op -> authorization (two approved humans,
        correlation, assessment+remediation, expiry, nonce) -> reconcile
        (refuse on Critical drift) -> adapter health -> data-feed health
        (fail-closed) -> TOCTOU re-verification -> Released -> Active commit.
        Original kill trigger cause is preserved; every refusal is recorded
        separately in the durable ledger. The gate + commit run under
        self._lock so the TOCTOU re-checks and the transition are atomic
        against the background poller thread.
        """
        if not self.risk_gate.kill_switch.blocks_routing():
            if self.logger:
                self.logger.info("engine", "Kill switch release: not held (no-op)")
            return

        with self._lock:
            # 0a) Authorization authority model (two approved humans, etc.).
            self._require_release_authorization(authorization)

            # 1) Held: refuse on genuine critical drift, with a reason code.
            result = self.reconcile()
            if result.severity is not None and result.severity == ReconciliationDriftSeverity.Critical:
                self._record_release_refusal("critical_reconcile_drift", {
                    "position_drifts": len(result.position_drifts),
                    "cash_drift": result.cash_drift,
                })
                raise RuntimeError(
                    f"Cannot release kill switch: "
                    f"kill_reason=critical_reconcile_drift "
                    f"({len(result.position_drifts)} position drifts, "
                    f"cash drift {result.cash_drift})"
                )

            # 2) Broker adapter health — an ADDITIONAL predicate, not the fix.
            if not self._check_adapter_health():
                self._record_release_refusal("adapter_down")
                raise RuntimeError("Cannot release kill switch: kill_reason=adapter_down")

            # 3) Verified control health (ADR-019): data-feed snapshot, fail-closed.
            verdict = self._evaluate_feed_health()
            if not verdict.healthy:
                self._record_release_refusal(verdict.reason, {"watermarks": verdict.watermarks})
                raise RuntimeError(f"Cannot release kill switch: kill_reason={verdict.reason}")

            # 4) TOCTOU: re-verify everything immediately before the commit,
            #    bypassing caches so the re-check is a fresh live read.
            if not self.risk_gate.kill_switch.is_triggered():
                self._record_release_refusal("state_changed")
                raise RuntimeError("Cannot release kill switch: kill_reason=state_changed")
            result2 = self.reconcile()
            if result2.severity is not None and result2.severity == ReconciliationDriftSeverity.Critical:
                self._record_release_refusal("critical_reconcile_drift_toctou")
                raise RuntimeError("Cannot release kill switch: kill_reason=critical_reconcile_drift_toctou")
            if not self._check_adapter_health(force=True):
                self._record_release_refusal("adapter_down_toctou")
                raise RuntimeError("Cannot release kill switch: kill_reason=adapter_down_toctou")
            verdict2 = self._evaluate_feed_health()
            if not verdict2.healthy:
                self._record_release_refusal(verdict2.reason, {"watermarks": verdict2.watermarks})
                raise RuntimeError(f"Cannot release kill switch: kill_reason={verdict2.reason}")

            # 5) Commit the transition: Triggered -> Releasing -> Released -> Active.
            #    Consume the nonce ONLY on success so a refusal (transient feed /
            #    adapter / reconcile hiccup) does not burn a still-valid record.
            if self.risk_gate.kill_switch.is_triggered():
                self.risk_gate.release_initiated()
            self.risk_gate.release_completed()
            if self.risk_gate.trading_state != TradingState.Active:
                self.risk_gate.set_trading_state(TradingState.Active)
            if authorization is not None and authorization.nonce:
                self._seen_release_nonces.add(authorization.nonce)
            self._save_state()
            try:
                self._event_store.append(EventEnvelope(
                    "KillSwitchReleased", "KillSwitchRelease", "system", "titan_python",
                    json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "correlation": self._kill_correlation,
                        "authorization_nonce": authorization.nonce if authorization else "",
                    }),
                ))
            except Exception:
                pass
            if self.logger:
                self.logger.info("engine", "Kill switch released")

    def _current_position_size(self, instrument_id: str) -> Optional[int]:
        pos = self.portfolio.get_position(instrument_id)
        return pos.quantity if pos is not None else None

    def _current_gross_exposure(self) -> Money:
        return self.portfolio.total_gross_exposure()

    def _calculate_portfolio_value(self, positions: list[Position], cash: Money) -> Money:
        from decimal import Decimal
        total = Decimal(cash.amount)
        for pos in positions:
            price_str = self._last_prices.get(pos.instrument_id)
            if not price_str:
                continue
            try:
                price = Decimal(price_str)
                if pos.side.__str__() == "Long":
                    total += Decimal(str(pos.quantity)) * price
                else:
                    total -= Decimal(str(pos.quantity)) * price
            except (Exception):
                pass
        return Money(str(total), self.config.currency)


def _pearson_correlation(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 3:
        return None
    ra = [(a[i] - a[i-1]) / a[i-1] for i in range(1, len(a))]
    rb = [(b[i] - b[i-1]) / b[i-1] for i in range(1, len(b))]
    n = len(ra)
    sum_x = sum(ra)
    sum_y = sum(rb)
    sum_xy = sum(x * y for x, y in zip(ra, rb))
    sum_x2 = sum(x * x for x in ra)
    sum_y2 = sum(y * y for y in rb)
    denom = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
    if abs(denom) < 1e-15:
        return None
    return max(-1.0, min(1.0, (n * sum_xy - sum_x * sum_y) / denom))
