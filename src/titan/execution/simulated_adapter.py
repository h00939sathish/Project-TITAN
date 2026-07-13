"""Simulated broker adapter for deterministic paper trading."""

from dataclasses import dataclass
from enum import Enum


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
    fills: list = None

    def __post_init__(self):
        self.fills = self.fills or []


class SimulatedAdapter:
    """A deterministic simulated broker adapter for paper trading.

    Never connects to an external system. Controlled entirely by test code
    via `set_fill_quality()` and `tick()`.
    """

    def __init__(self):
        self._orders: dict[str, SimOrderState] = {}
        self._fill_quality: dict[str, SimFillQuality] = {}
        self._default_fill_quality = SimFillQuality.IMMEDIATE_FULL
        self._current_time = "2026-01-01T00:00:00Z"

    def set_default_fill_quality(self, quality: SimFillQuality):
        self._default_fill_quality = quality

    def set_fill_quality(self, order_id: str, quality: SimFillQuality):
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
            state.status = "pending"
        elif quality == SimFillQuality.NEVER_FILL:
            state.status = "pending"

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

    def _apply_fill(self, state: SimOrderState, quantity: int):
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
