"""Time-Weighted Average Price (TWAP) execution algorithm."""

import time
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from titan._core import ApprovedOrderIntent
if TYPE_CHECKING:
    from titan.execution.engine import PaperTradingEngine
from titan.execution.order_state import OrderState, OrderStateMachine


@dataclass
class TWAPConfig:
    slices: int = 5
    duration_seconds: int = 60


class TWAPExecutor:
    def __init__(self, engine: "PaperTradingEngine", config: TWAPConfig | None = None):
        self.engine = engine
        self.config = config or TWAPConfig()
        self._threads: list[threading.Thread] = []

    def execute(self, parent: ApprovedOrderIntent) -> None:
        """Slices the parent order and submits child orders in a background thread."""
        t = threading.Thread(target=self._run_twap, args=(parent,), daemon=True)
        self._threads.append(t)
        t.start()

    def _run_twap(self, parent: ApprovedOrderIntent) -> None:
        total_qty = int(parent.quantity)
        n_slices = self.config.slices
        base_slice = total_qty // n_slices
        remainder = total_qty % n_slices
        interval = self.config.duration_seconds / n_slices

        for i in range(n_slices):
            if self.engine.risk_gate.kill_switch.blocks_routing():
                if self.engine.logger:
                    self.engine.logger.warning("twap", f"TWAP {parent.client_order_id} aborted due to kill switch")
                break

            qty = base_slice + (1 if i < remainder else 0)
            if qty <= 0:
                continue

            child_client_order_id = f"{parent.client_order_id}-slice-{i}"
            
            child = ApprovedOrderIntent(
                risk_decision_id=parent.risk_decision_id,
                intent_id=parent.intent_id,
                client_order_id=child_client_order_id,
                instrument_id=parent.instrument_id,
                side=parent.side,
                quantity=str(qty),
                order_type=parent.order_type,
                time_in_force=parent.time_in_force,
                risk_profile_version=parent.risk_profile_version,
                price=parent.price,
                stop_price=parent.stop_price,
            )

            # Register state in engine
            sm = OrderStateMachine()
            sm.transition(OrderState.Validated)
            sm.transition(OrderState.Submitted)
            
            with self.engine._lock:
                self.engine.order_states[child_client_order_id] = sm
                self.engine._order_metadata[child_client_order_id] = {
                    "instrument_id": child.instrument_id,
                    "side": child.side,
                    "quantity": int(child.quantity),
                    "price": child.price,
                    "order_type": child.order_type,
                    "parent_id": parent.client_order_id,
                }
            
            try:
                acknowledgement = self.engine.adapter.place_order(child)
                with self.engine._lock:
                    if acknowledgement.accepted:
                        sm.transition(OrderState.Acknowledged)
                        if acknowledgement.broker_order_id:
                            self.engine.order_states[str(acknowledgement.broker_order_id.id)] = sm
                            self.engine._order_metadata[str(acknowledgement.broker_order_id.id)] = self.engine._order_metadata[child_client_order_id]
                    else:
                        sm.transition(OrderState.Rejected)
                        if self.engine.logger:
                            self.engine.logger.warning("twap", f"Child order {child_client_order_id} rejected: {acknowledgement.rejection_reason}")
            except Exception as e:
                with self.engine._lock:
                    sm.transition(OrderState.Rejected)
                if self.engine.logger:
                    self.engine.logger.error("twap", f"Broker submit failed for child {child_client_order_id}: {e}")

            if i < n_slices - 1:
                time.sleep(interval)