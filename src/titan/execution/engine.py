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
from typing import Optional

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
from titan.risk.session_initialization import (
    SessionInitialization,
    validate as validate_initialization,
)

# Order statuses that mean "still alive at the broker" — a working order must
# NEVER be rejected/cancelled locally (the broker may fill it any moment).
_WORKING_ORDER_STATUSES = frozenset({
    "Submitted", "PreSubmitted", "PendingSubmit", "PendingCancel",
})
# Terminal statuses where the broker will take no further action.
_DEAD_ORDER_STATUSES = frozenset({
    "Filled", "Rejected", "Cancelled", "Inactive", "ApiCancelled", "ApiRejected",
})
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


class PaperTradingEngine:
    """End-to-end paper trading engine.

    Wires together: Strategy → RiskGate → Adapter → PortfolioEngine → ReconciliationEngine.
    """

    def __init__(self, config: PaperConfig, adapter: BrokerAdapter,
                 logger: Optional[StructuredLogger] = None):
        self.config = config
        self.adapter = adapter
        self.logger = logger
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

        self.order_states: dict[str, OrderStateMachine] = {}
        self.instruments: dict[str, Instrument] = {}
        self._session: Optional[Session] = None
        self._intent_counter: int = 0
        self._health_cache: Optional[tuple[float, bool]] = None
        self._health_cache_ttl = 5.0
        self._seen_init_nonces: set[str] = set()
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
            if not self.risk_gate.kill_switch.blocks_routing():
                self.risk_gate.trigger_kill_switch()
                kill_switch_triggered.inc()
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
                self.risk_gate.trigger_kill_switch()

        saved_pnl = pf.get("realized_pnl", {})
        if saved_pnl and saved_pnl["amount"] != self.portfolio.realized_pnl.amount:
            self.portfolio.set_realized_pnl(
                Money(saved_pnl["amount"], saved_pnl["currency"])
            )

    def _save_state(self) -> None:
        if not self.config.state_path:
            return

        state = self._build_state_dict()
        path = Path(self.config.state_path)
        try:
            with self._lock:
                path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

        self._append_state_snapshot()
        try:
            self.risk_gate.persist_state(self._event_store)
        except Exception:
            pass

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
                if not self.risk_gate.kill_switch.blocks_routing():
                    self.risk_gate.trigger_kill_switch()
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

    def _check_adapter_health(self) -> bool:
        """Check adapter health. Returns True if healthy, False if down.

        On first failure, auto-triggers kill switch (fail-closed).
        """
        now = time.monotonic()
        if self._health_cache and (now - self._health_cache[0]) < self._health_cache_ttl:
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

    def submit_intent(self, intent: TradeIntent, *, correlation_id: str = "") -> OrderResult:
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

        # TWAP: split large orders into slices
        qty = int(intent.quantity)
        if self.config.use_twap and qty > 50:
            from titan.execution.twap import TWAPExecutor, TWAPConfig
            twap_config = TWAPConfig(slices=self.config.twap_slice_count, duration_seconds=self.config.twap_duration_seconds)
            twap = TWAPExecutor(self, twap_config)
            twap.execute(approved)
            # The background thread handles child order submissions and tracking.
            # Mark the parent order as acknowledged conceptually.
            sm.transition(OrderState.Acknowledged)
            return OrderResult(
                accepted=True,
                rejection_reason="",
            )
        else:
            try:
                acknowledgement = self.adapter.place_order(approved)
            except Exception as e:
                self.rejections_by_instrument[instr_str] += 1
                sm.transition(OrderState.Rejected)
                sm.persist_transition(self._event_store, client_order_id, OrderState.Submitted, OrderState.Rejected, f"broker_error: {e}")
                if self.logger:
                    self.logger.error("engine", f"Broker submit failed: {e}")
                orders_rejected.inc()
                if not self.risk_gate.kill_switch.blocks_routing():
                    self.trigger_kill_switch()
                return OrderResult(
                    accepted=False,
                    rejection_reason=f"Broker submit failed: {e}",
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

        # Track metadata for ALL accepted orders (filled AND still-working) so
        # poll_fills can absorb async fills, partial fills and external cancels.
        total_qty = int(str(approved.quantity))
        self._order_metadata[client_order_id] = {
            "instrument_id": str(intent.instrument_id),
            "side": str(intent.side),
            "quantity": total_qty,
        }
        self._order_filled_quantity.setdefault(client_order_id, 0)

        fills = self._resolve_fills(approved, broker_id, acknowledgement)
        if fills:
            total_filled = 0
            for fill in fills:
                qty = int(fill.quantity) if fill.quantity else 0
                if qty <= 0:
                    continue
                total_filled += qty
                old_pos = self.portfolio.get_position(fill.instrument_id)
                old_side = str(old_pos.side) if old_pos else "None"
                old_qty = old_pos.quantity if old_pos else 0

                self.portfolio.apply_fill(
                    instrument_id=fill.instrument_id,
                    side=fill.side.lower(),
                    quantity=qty,
                    price=Money(fill.price, self.config.currency),
                )
                self.update_price(fill.instrument_id, fill.price)
                orders_filled.inc()
                self.fills_by_instrument[fill.instrument_id] += 1


                new_pos = self.portfolio.get_position(fill.instrument_id)
                new_side = str(new_pos.side) if new_pos else "None"
                if old_pos is None or old_pos.quantity == 0:
                    evt_type = "PositionOpened"
                elif new_pos is not None and new_pos.quantity == 0:
                    evt_type = "PositionClosed"
                else:
                    evt_type = "PositionChanged"
                self._event_store.append(EventEnvelope(
                    evt_type, "Portfolio", fill.instrument_id, "titan_python",
                    json.dumps({
                        "instrument_id": fill.instrument_id,
                        "old_side": old_side,
                        "old_quantity": old_qty,
                        "side": fill.side,
                        "quantity": qty,
                        "price": fill.price,
                    }),
                ))
                self._event_store.append(EventEnvelope(
                    "OrderFilled", "Execution", client_order_id, "titan_python",
                    json.dumps({
                        "client_order_id": client_order_id,
                        "instrument_id": fill.instrument_id,
                        "side": fill.side,
                        "filled_quantity": qty,
                        "fill_price": fill.price,
                    }),
                ))

            self._order_filled_quantity[client_order_id] = total_filled
            if total_filled < total_qty:
                sm.transition(OrderState.PartiallyFilled)
                sm.persist_transition(self._event_store, client_order_id, OrderState.Acknowledged, OrderState.PartiallyFilled, "partial_fill")
            else:
                sm.transition(OrderState.Filled)
                sm.persist_transition(self._event_store, client_order_id, OrderState.Acknowledged, OrderState.Filled, "full_fill")
        else:
            ack_status = getattr(acknowledgement, "order_status", None) or ""
            if ack_status in _WORKING_ORDER_STATUSES:
                # Order is still working at the broker (Submitted/PreSubmitted) —
                # the engine's fill timeout elapsed before a terminal status.
                # Keep the order PENDING: poll_fills absorbs the fill or external
                # cancel asynchronously via adapter.tick(). Never assume it dead.
                if self.logger:
                    log_adapter_event(self.logger, "order_working", client_order_id,
                                      instrument_id=str(intent.instrument_id),
                                      payload={"status": ack_status})
            else:
                sm.transition(OrderState.Rejected)
                sm.persist_transition(self._event_store, client_order_id, OrderState.Acknowledged, OrderState.Rejected, "no_fill_quantity")
                if self.logger:
                    log_adapter_event(self.logger, "fill_failed", client_order_id,
                                      instrument_id=str(intent.instrument_id),
                                      payload={"reason": "no_fill_quantity"})
                # The broker may still be working this order or may fill it after our
                # timeout. Cancel it so TWS does not fill an order the engine already
                # declared dead — otherwise positions drift (TWS holds what the engine
                # thinks never existed).
                if broker_id is not None:
                    try:
                        self.adapter.cancel(broker_id)
                    except Exception:
                        pass


        self._save_state()
        if fills and self.logger:
            log_adapter_event(self.logger, "filled", client_order_id,
                              instrument_id=str(intent.instrument_id),
                              payload={"fills": len(fills), "qty": str(intent.quantity)})

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
        """Check all open Acknowledged/PartiallyFilled orders for new fills from the adapter.
        Should be called periodically (e.g. on every market-data tick).
        """
        import copy
        with self._lock:
            open_orders = list(self.order_states.items())

        for order_id, sm in open_orders:
            with self._lock:
                if sm.current not in (OrderState.Acknowledged, OrderState.PartiallyFilled):
                    self._order_metadata.pop(order_id, None)
                    self._order_filled_quantity.pop(order_id, None)
                    continue

                meta = self._order_metadata.get(order_id)
                already_filled = self._order_filled_quantity.get(order_id, 0)
                # pyo3 enum objects are immutable — a plain reference is fine
                # (deepcopy raises TypeError: cannot pickle OrderState).
                from_state = sm.current

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

            status = str(getattr(result, "status", "") or "")
            if status in _DEAD_ORDER_STATUSES and status != "Filled":
                # Terminal dead state reached outside the synchronous wait —
                # typically an external cancel/reject from the TWS UI or a
                # rejected fill. Transition the order and drop tracking.
                with self._lock:
                    try:
                        sm.transition(OrderState.Rejected)
                        sm.persist_transition(
                            self._event_store, order_id, from_state,
                            OrderState.Rejected, f"broker_{status.lower()}",
                        )
                    except Exception:
                        pass
                    self._order_metadata.pop(order_id, None)
                    self._order_filled_quantity.pop(order_id, None)
                log_adapter_event(self.logger, "broker_dead_order", order_id,
                                  payload={"status": status, "instrument_id": result.instrument_id})
                continue
            if status not in ("Filled", ""):
                # Still working at the broker — nothing to do this poll.
                continue

            new_qty = int(result.filled_quantity or 0) - already_filled
            if new_qty <= 0:
                continue

            fill_price = result.price or "0"
            fill = BrokerFill(
                execution_id=str(uuid.uuid4()),
                order_id=BrokerOrderId(id=order_id),
                instrument_id=result.instrument_id,
                side=result.side.upper(),
                quantity=str(new_qty),
                price=fill_price,
                fees=Money("0", self.config.currency),
                currency=self.config.currency,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            with self._lock:
                old_pos = self.portfolio.get_position(fill.instrument_id)
                old_side = str(old_pos.side) if old_pos else "None"
                old_qty = old_pos.quantity if old_pos else 0

                self.portfolio.apply_fill(
                    instrument_id=fill.instrument_id,
                    side=fill.side.lower(),
                    quantity=int(fill.quantity),
                    price=Money(fill.price, self.config.currency),
                )
                self._last_prices[fill.instrument_id] = fill.price
                orders_filled.inc()

                new_pos = self.portfolio.get_position(fill.instrument_id)
                if old_pos is None or old_pos.quantity == 0:
                    evt_type = "PositionOpened"
                elif new_pos is not None and new_pos.quantity == 0:
                    evt_type = "PositionClosed"
                else:
                    evt_type = "PositionChanged"
                self._event_store.append(EventEnvelope(
                    evt_type, "Portfolio", fill.instrument_id, "titan_python",
                    json.dumps({
                        "instrument_id": fill.instrument_id,
                        "old_side": old_side,
                        "old_quantity": old_qty,
                        "side": fill.side,
                        "quantity": int(fill.quantity),
                        "price": fill.price,
                    }),
                ))

                self._order_filled_quantity[order_id] = int(result.filled_quantity or 0)
                total_qty = meta.get("quantity", 0)

                if int(result.filled_quantity or 0) < total_qty:
                    if from_state == OrderState.Acknowledged:
                        sm.transition(OrderState.PartiallyFilled)
                        sm.persist_transition(self._event_store, order_id, from_state, OrderState.PartiallyFilled, "partial_fill_from_poll")
                else:
                    sm.transition(OrderState.Filled)
                    sm.persist_transition(self._event_store, order_id, from_state, OrderState.Filled, "full_fill_from_poll")
                if self.logger:
                    log_adapter_event(self.logger, "filled_from_poll", order_id,
                                      instrument_id=fill.instrument_id,
                                      payload={"new_qty": new_qty, "total": result.filled_quantity})

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
                if not self.risk_gate.kill_switch.blocks_routing():
                    self.risk_gate.trigger_kill_switch()
                    kill_switch_triggered.inc()
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

            return EngineStatus(
                trading_state=self.risk_gate.trading_state,
                kill_switch=self.risk_gate.kill_switch,
                positions=positions,
                cash_balance=cash,
                portfolio_value=pv,
                open_orders=open_count,
                adapter_health=health,
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

    def trigger_kill_switch(self) -> None:

        self.risk_gate.trigger_kill_switch()
        self._save_state()
        kill_switch_triggered.inc()
        if self.logger:
            self.logger.warning("engine", "Kill switch triggered")

    def _record_init_refusal(self, reason: str) -> None:
        """Durable audit record for a refused initialization."""
        try:
            self._event_store.append(EventEnvelope(
                "InitializationRefused", "SessionInitialization", "system",
                "titan_python",
                json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                            "reason": reason}),
            ))
        except Exception:
            pass
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
        reason = validate_initialization(initialization, self._seen_init_nonces)
        if reason:
            self._record_init_refusal(reason)
            raise RuntimeError(f"Cannot initialize session: kill_reason={reason}")
        if self._event_store.replay_by_type("RiskStateSnapshot"):
            self._record_init_refusal("initialization_conflicts_with_existing_state")
            raise RuntimeError(
                "Cannot initialize session: kill_reason="
                "initialization_conflicts_with_existing_state")
        with self._lock:
            self.risk_gate.initialize_armed()
            self._seen_init_nonces.add(initialization.nonce)
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
            self._save_state()
            if self.logger:
                self.logger.info("engine", "Session initialized (explicit, audited)")

    def release_kill_switch(self) -> None:
        """Resume a halted session.

        Idempotent by design: if the kill switch is not held (state Armed or
        Released), the release is a no-op and returns cleanly instead of
        trying an illegal state transition (the Rust machine only allows
        Triggered -> Releasing -> Released). When held, it reconciles first
        and refuses on critical drift, surfacing a structured reason so a
        caller can echo why the release was denied.
        """
        # 1) Not held -> nothing to release. No-op, not an error.
        if not self.risk_gate.kill_switch.blocks_routing():
            if self.logger:
                self.logger.info("engine", "Kill switch release: not held (no-op)")
            return

        # 2) Held: refuse on genuine critical drift, with a reason code.
        result = self.reconcile()
        if result.severity is not None and result.severity == ReconciliationDriftSeverity.Critical:
            raise RuntimeError(
                f"Cannot release kill switch: "
                f"kill_reason=critical_reconcile_drift "
                f"({len(result.position_drifts)} position drifts, "
                f"cash drift {result.cash_drift})"
            )

        # 3) Complete the transition. Covers both held states: Triggered needs
        #    the initiator step, Releasing jumps straight to completion.
        if self.risk_gate.kill_switch.is_triggered():
            self.risk_gate.release_initiated()
        self.risk_gate.release_completed()
        if self.risk_gate.trading_state != TradingState.Active:
            self.risk_gate.set_trading_state(TradingState.Active)
        self._save_state()
        if self.logger:
            self.logger.info("engine", "Kill switch released")

    def _resolve_fills(
        self,
        intent: ApprovedOrderIntent,
        broker_id: Optional[BrokerOrderId],
        ack: Optional[BrokerOrderAcknowledgement] = None,
    ) -> list[BrokerFill]:
        if ack is None:
            return []
        raw_qty = ack.fill_quantity
        if not raw_qty or str(raw_qty) == "0":
            return []
        fill_price = ack.fill_price if ack.fill_price else (str(intent.price) if intent.price else "0")
        fill = BrokerFill(
            execution_id=str(uuid.uuid4()),
            order_id=broker_id or BrokerOrderId(id="unknown"),
            instrument_id=str(intent.instrument_id),
            side=str(intent.side),
            quantity=str(raw_qty),
            price=fill_price,
            fees=Money("0", self.config.currency),
            currency=self.config.currency,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return [fill]

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
