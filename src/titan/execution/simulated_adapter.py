"""Simulated broker adapter for deterministic paper trading."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from titan._core import ApprovedOrderIntent, BrokerPosition, Money

from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)


class SimFillQuality(Enum):
    """Controls fill behavior for deterministic testing."""
    IMMEDIATE_FULL = "immediate_full"
    PARTIAL_THEN_FULL = "partial_then_full"
    REJECT = "reject"
    TIMEOUT = "timeout"
    NEVER_FILL = "never_fill"


@dataclass
class SimOrderState:
    """Track a simulated order's lifecycle."""
    order_id: str
    instrument_id: str
    side: str
    quantity: int
    price: str
    status: str
    filled_quantity: int = 0
    fills: list[Any] = field(default_factory=list)


class SimulatedAdapter(BrokerAdapter):
    """A deterministic simulated broker adapter for paper trading.

    Never connects to an external system. Controlled entirely by test code
    via `set_fill_quality()` and `tick()`.
    """

    def __init__(self) -> None:
        self._orders: dict[str, SimOrderState] = {}
        self._fill_quality: dict[str, SimFillQuality] = {}
        self._default_fill_quality = SimFillQuality.IMMEDIATE_FULL
        self._current_time = "2026-01-01T00:00:00Z"

    def authenticate(self) -> Session:
        return Session(
            session_id=str(uuid.uuid4()),
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def heartbeat(self) -> AdapterHealth:
        return AdapterHealth(connected=True, session_state=AdapterSessionState.CONNECTED)

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        price = str(intent.price) if intent.price else "0"
        order = self.submit_order(
            order_id=str(intent.client_order_id) if intent.client_order_id else str(uuid.uuid4()),
            instrument_id=str(intent.instrument_id),
            side=str(intent.side).lower(),
            quantity=int(str(intent.quantity)),
            price=price,
        )
        return BrokerOrderAcknowledgement(
            accepted=order.status != "rejected",
            broker_order_id=BrokerOrderId(id=order.order_id),
            rejection_reason="Simulated rejection" if order.status == "rejected" else None,
            fill_price=price if order.status == "filled" else None,
            fill_quantity=str(order.filled_quantity) if order.filled_quantity > 0 else None,
            order_status=order.status,
        )

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        net: dict[str, int] = {}
        for o in self._orders.values():
            if o.filled_quantity <= 0:
                continue
            qty = o.filled_quantity if o.side == "buy" else -o.filled_quantity
            net[o.instrument_id] = net.get(o.instrument_id, 0) + qty
        positions = [
            BrokerPosition(
                instrument_id=inst,
                side="LONG" if qty > 0 else "SHORT",
                quantity=abs(qty),
            )
            for inst, qty in net.items()
            if qty != 0
        ]
        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=positions,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        cash = Decimal("100000")
        for o in self._orders.values():
            if o.filled_quantity <= 0:
                continue
            price = Decimal(str(o.price))
            total = price * o.filled_quantity
            if o.side == "buy":
                cash -= total
            else:
                cash += total
        cash_money = Money(str(cash), "USD")
        return BrokerBalanceSnapshot(
            account_id=account_id,
            currency="USD",
            cash=cash_money,
            portfolio_value=cash_money,
            buying_power=cash_money,
            equity=cash_money,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        success = self.cancel_order(order_id.id)
        return CancellationAcknowledgement(accepted=success, broker_order_id=order_id)

    def set_default_fill_quality(self, quality: SimFillQuality) -> None:
        self._default_fill_quality = quality

    def set_fill_quality(self, order_id: str, quality: SimFillQuality) -> None:
        self._fill_quality[order_id] = quality

    def submit_order(self, order_id: str, instrument_id: str, side: str,
                     quantity: int, price: str) -> SimOrderState:
        """Submit an order and process according to fill quality."""
        quality = self._fill_quality.get(order_id, self._default_fill_quality)

        state = SimOrderState(
            order_id=order_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=price,
            status="pending",
        )

        if quality == SimFillQuality.REJECT:
            state.status = "rejected"
        elif quality == SimFillQuality.IMMEDIATE_FULL:
            self._apply_fill(state, quantity)
        elif quality == SimFillQuality.PARTIAL_THEN_FULL:
            self._apply_fill(state, quantity // 2)
        elif quality == SimFillQuality.TIMEOUT:
            raise AdapterError(
                f"Simulated timeout submitting order {order_id} after 5000ms",
                "timeout",
            )

        self._orders[order_id] = state
        return state

    def tick(self, order_id: str) -> SimOrderState | None:
        """Advance time for a pending or partially filled order. Returns updated order or None."""
        state = self._orders.get(order_id)
        if not state or state.status in ("filled", "rejected", "cancelled"):
            return None

        quality = self._fill_quality.get(order_id, self._default_fill_quality)

        if quality == SimFillQuality.PARTIAL_THEN_FULL and state.filled_quantity > 0:
            remaining = state.quantity - state.filled_quantity
            self._apply_fill(state, remaining)
        elif quality == SimFillQuality.NEVER_FILL:
            return None

        return state

    def get_order(self, order_id: str) -> SimOrderState | None:
        return self._orders.get(order_id)

    def cancel_order(self, order_id: str) -> bool:
        state = self._orders.get(order_id)
        if state and state.status in ("pending", "partially_filled"):
            state.status = "cancelled"
            return True
        return False

    def _apply_fill(self, state: SimOrderState, quantity: int) -> None:
        state.filled_quantity += quantity
        fill_price = float(state.price) if state.price else 0.0
        state.fills.append({
            "time": self._current_time,
            "quantity": quantity,
            "price": fill_price,
        })
        if state.filled_quantity >= state.quantity:
            state.status = "filled"
        else:
            state.status = "partially_filled"

    @property
    def open_orders(self) -> list[SimOrderState]:
        return [o for o in self._orders.values() if o.status in ("pending", "partially_filled")]

    @property
    def filled_orders(self) -> list[SimOrderState]:
        return [o for o in self._orders.values() if o.status == "filled"]

    def save_order_count_state(self) -> dict:
        return {}

    def restore_order_count_state(self, state: dict) -> None:
        pass
