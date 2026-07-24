import json
import os
import time
import uuid
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
        store_path = config.state_path.replace(".json", ".db") if config.state_path else ".titan_state.db"
        self._event_store = EventStore(store_path)
        self.risk_gate = RiskGate(config.risk_config)
        try:
            self.risk_gate.restore_state(self._event_store)
        except Exception:
            pass
        self.portfolio = PortfolioEngine(config.currency, Money(config.starting_capital, config.currency))

        recon_config = config.reconciliation_config or ReconciliationConfig()
        self.reconciler = ReconciliationEngine(recon_config)

        self.order_states: dict[str, OrderStateMachine] = {}
        self.instruments: dict[str, Instrument] = {}
        self._session: Optional[Session] = None
        self._intent_counter: int = 0
        self._health_cache: Optional[tuple[float, bool]] = None
        self._health_cache_ttl = 5.0
        self._last_prices: dict[str, str] = {}
        self._order_metadata: dict[str, dict] = {}
        self._order_filled_quantity: dict[str, int] = {}
        self._decision_traces: dict[str, list[dict]] = {}

    def _restore_order_states(self) -> None:
        try:
            events = self._event_store.replay_by_type("OrderTransition")
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
                payload = json.loads(ev.payload)
                order_id = payload["order_id"]
                to_state_str = payload["to_state"]
                if order_id not in self.order_states:
                    self.order_states[order_id] = OrderStateMachine()
                target = state_map.get(to_state_str)
                if target is not None:
                    try:
                        self.order_states[order_id].transition(target)
                    except Exception:
                        self.order_states[order_id].reset_to(target)
        except Exception:
            pass

    def start(self, sync_from_broker: bool = False) -> Session:
        self._session = self.adapter.authenticate()
        loaded = self._load_state()
        self._restore_order_states()
        if sync_from_broker:
            self._sync_from_broker()
        self._save_state()
        if self.logger:
            self.logger.info("engine", "Session started",
                             payload={"account_id": self.config.account_id,
                                      "state_loaded": "synced" if sync_from_broker else str(loaded)})
        return self._session

    def _sync_from_broker(self) -> None:
        broker_cash = None
        broker_positions = []
        try:
            bal = self.adapter.holdings(self.config.account_id)
            broker_cash = bal.cash
        except Exception:
            pass
        try:
            pos_snap = self.adapter.positions(self.config.account_id)
            broker_positions = pos_snap.positions
        except Exception:
            pass

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

    def _save_state(self) -> None:
        if not self.config.state_path:
            return
        path = Path(self.config.state_path)
        tmp = path.with_suffix(".tmp")
        state = {
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
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        try:
            with open(tmp, "r+b") as f:
                os.fsync(f.fileno())
        except OSError as e:
            if self.logger:
                self.logger.error("engine", f"State persistence fsync failed: {e}")
            if not self.risk_gate.kill_switch.blocks_routing():
                self.risk_gate.trigger_kill_switch()
            return
        os.replace(str(tmp), str(path))
        try:
            self.risk_gate.persist_state(self._event_store)
        except Exception:
            pass

    def _load_state(self) -> bool:
        if not self.config.state_path:
            return False
        path = Path(self.config.state_path)
        if not path.exists():
            return False
        try:
            state = json.loads(path.read_text())
        except (json.JSONDecodeError, KeyError):
            if self.logger:
                self.logger.error("engine", "Corrupt state file — halting routing")
            self.risk_gate.trigger_kill_switch()
            return True  # state was loaded (halted)

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
            self.portfolio.apply_fill(
                instrument_id=pos_data["instrument_id"],
                side=fill_side,
                quantity=qty,
                price=Money("0", pf["cash"]["currency"]),
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
            if not isinstance(oc, dict):
                if self.logger:
                    self.logger.error("engine", "Corrupt order_count state — halting routing")
                self.risk_gate.trigger_kill_switch()
            else:
                self.adapter.restore_order_count_state(oc)

        saved_pnl = pf.get("realized_pnl", {})
        if saved_pnl and saved_pnl["amount"] != self.portfolio.realized_pnl.amount:
            self.portfolio.set_realized_pnl(
                Money(saved_pnl["amount"], saved_pnl["currency"])
            )

        return True

    def stop(self) -> None:
        self._save_state()
        try:
            self.adapter.heartbeat()
        except Exception:
            pass
        self._session = None
        if self.logger:
            self.logger.info("engine", "Session stopped")

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

    def submit_intent(self, intent: TradeIntent, *, correlation_id: str = "") -> OrderResult:
        if not self._check_adapter_health():
            return OrderResult(accepted=False, rejection_reason="Adapter unhealthy — trading halted")

        if not TradingState.Active.accepts_intents():
            if self.logger:
                self.logger.warning("engine", "Intent rejected: trading not active")
            return OrderResult(accepted=False, rejection_reason="Trading state is not active")

        if self.risk_gate.kill_switch.blocks_routing():
            if self.logger:
                self.logger.warning("engine", "Intent rejected: kill switch blocking")
            return OrderResult(accepted=False, rejection_reason="Kill switch is blocking routing")

        instr_id = str(intent.instrument_id)
        instrument = self.instruments.get(instr_id)
        if instrument is None:
            return OrderResult(accepted=False, rejection_reason=f"Instrument is not registered: {instr_id}")
        raw = instrument.validate_order(intent.side or "BUY", int(intent.quantity), intent.price or "0")
        if raw is not None:
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
        verdict = self.risk_gate.evaluate(
            intent,
            self._current_position_size(intent.instrument_id),
            self._current_gross_exposure(),
            snapshot.drawdown_fraction,
            snapshot.daily_realized_loss,
            pos_side,
        )

        if not verdict.accepted:
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

        orders_submitted.inc()
        try:
            acknowledgement = self.adapter.place_order(approved)
        except Exception as e:
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
        self._trace_decision(correlation_id, "BrokerAcknowledgement",
                             {"broker_order_id": str(broker_id.id) if broker_id else None,
                              "client_order_id": client_order_id,
                              "accepted": True})

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
                self._last_prices[fill.instrument_id] = fill.price
                orders_filled.inc()

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

            total_qty = int(str(approved.quantity))
            self._order_metadata[client_order_id] = {
                "instrument_id": str(intent.instrument_id),
                "side": str(intent.side),
                "quantity": total_qty,
            }
            self._order_filled_quantity[client_order_id] = total_filled
            sm.transition(OrderState.PartiallyFilled)
            sm.persist_transition(self._event_store, client_order_id, OrderState.Acknowledged, OrderState.PartiallyFilled, "partial_fill")
            if total_filled >= total_qty:
                sm.transition(OrderState.Filled)
                sm.persist_transition(self._event_store, client_order_id, OrderState.PartiallyFilled, OrderState.Filled, "full_fill")
        else:
            sm.transition(OrderState.Rejected)
            sm.persist_transition(self._event_store, client_order_id, OrderState.Acknowledged, OrderState.Rejected, "no_fill_quantity")
            if self.logger:
                log_adapter_event(self.logger, "fill_failed", client_order_id,
                                  instrument_id=str(intent.instrument_id),
                                  payload={"reason": "no_fill_quantity"})

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
        for order_id, sm in list(self.order_states.items()):
            if sm.current not in (OrderState.Acknowledged, OrderState.PartiallyFilled):
                self._order_metadata.pop(order_id, None)
                self._order_filled_quantity.pop(order_id, None)
                continue

            meta = self._order_metadata.get(order_id)
            if meta is None:
                continue

            try:
                result = self.adapter.tick(order_id)
            except Exception:
                continue
            if result is None:
                continue

            already_filled = self._order_filled_quantity.get(order_id, 0)
            new_qty = result.filled_quantity - already_filled
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

            self._order_filled_quantity[order_id] = result.filled_quantity
            total_qty = meta.get("quantity", 0)
            from_state = copy.deepcopy(sm.current)

            sm.transition(OrderState.Filled)
            sm.persist_transition(self._event_store, order_id, from_state, OrderState.Filled, "full_fill_from_poll")
            if self.logger:
                log_adapter_event(self.logger, "filled_from_poll", order_id,
                                  instrument_id=fill.instrument_id,
                                  payload={"new_qty": new_qty, "total": result.filled_quantity})

    def reconcile(self) -> ReconciliationResult:
        broker_positions = []
        try:
            pos_snapshot = self.adapter.positions(self.config.account_id)
            broker_positions = pos_snapshot.positions
        except Exception as e:
            if self.logger:
                self.logger.warning("engine", f"Reconcile: position fetch failed: {e}")

        broker_cash = Money("0", self.config.currency)
        try:
            bal_snapshot = self.adapter.holdings(self.config.account_id)
            broker_cash = bal_snapshot.cash
        except Exception as e:
            if self.logger:
                self.logger.warning("engine", f"Reconcile: holdings fetch failed: {e}")

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
        gross_exposure.set(float(sum(abs(p.quantity) for p in positions)))

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

    def trigger_kill_switch(self) -> None:
        self.risk_gate.trigger_kill_switch()
        self._save_state()
        kill_switch_triggered.inc()
        if self.logger:
            self.logger.warning("engine", "Kill switch triggered")

    def release_kill_switch(self) -> None:
        result = self.reconcile()
        if result.severity is not None and result.severity == ReconciliationDriftSeverity.Critical:
            raise RuntimeError(
                f"Cannot release kill switch: critical reconciliation drift "
                f"({len(result.position_drifts)} position drifts, "
                f"cash drift {result.cash_drift})"
            )
        self.risk_gate.release_initiated()
        self.risk_gate.release_completed()
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

    def _current_gross_exposure(self) -> Optional[Money]:
        total = 0
        for instr in self.config.risk_config.instrument_eligibility:
            pos = self.portfolio.get_position(instr)
            if pos is not None:
                total += abs(pos.quantity)
        return Money(str(total), self.config.currency)

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
