"""Fincept Terminal broker adapter for Project TITAN.

Bridges TITAN's execution and risk pipeline directly with Fincept Terminal's
C++ broker integrations, paper engine, and market data via fincept_native.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Optional

from titan._core import ApprovedOrderIntent, BrokerPosition, Money
from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    Session,
)

# Attempt to import fincept_native; graceful fallback for testing/mocking
try:
    import fincept_native as fn
except ImportError:
    fn = None


class FinceptBrokerAdapter(BrokerAdapter):
    """Adapter connecting TITAN's PaperTradingEngine / ExecutionEngine to Fincept Terminal.

    Orders emitted as ApprovedOrderIntent are converted to fincept_native.trading.UnifiedOrder
    and executed via UnifiedTrading or PaperTrading in-process with zero IPC overhead.
    """

    def __init__(
        self,
        account_id: str = "paper-1",
        default_exchange: str = "NSE",
        currency: str = "INR",
        native_module: Optional[Any] = None,
    ) -> None:
        self.account_id = account_id
        self.default_exchange = default_exchange
        self.currency = currency
        self._fn = native_module if native_module is not None else fn
        self._connected = False
        self._session: Optional[Session] = None
        self._orders: dict[str, dict[str, Any]] = {}

    def authenticate(self) -> Session:
        """Authenticate with Fincept runtime and verify broker/paper environment."""
        if self._fn is None:
            raise AdapterError(
                "fincept_native module not found. Run within Fincept Terminal or mock native_module.",
                "import_error",
            )

        try:
            health = self._fn.runtime.health()
            if not health.get("embedded", False):
                raise AdapterError("fincept_native reports embedded=False", "runtime_error")
        except Exception as e:
            raise AdapterError(f"Fincept health check failed: {e}", "auth_failed")

        self._connected = True
        self._session = Session(
            session_id=f"fincept-{self.account_id}-{uuid.uuid4().hex[:8]}",
            state=AdapterSessionState.CONNECTED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return self._session

    def heartbeat(self) -> AdapterHealth:
        """Check connection health of the Fincept runtime."""
        if not self._connected or self._fn is None:
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=["Fincept runtime not connected"],
            )

        try:
            health = self._fn.runtime.health()
            is_healthy = bool(health.get("embedded", False))
            return AdapterHealth(
                connected=is_healthy,
                session_state=AdapterSessionState.CONNECTED if is_healthy else AdapterSessionState.DISCONNECTED,
                degradation=[] if is_healthy else ["Runtime unhealthy"],
            )
        except Exception as e:
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=[str(e)],
            )

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        """Convert a TITAN ApprovedOrderIntent into Fincept's UnifiedOrder and place it."""
        if not self._connected or self._fn is None:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason="FinceptBrokerAdapter not connected",
            )

        # Parse symbol and exchange
        raw_symbol = str(intent.instrument_id)
        if ":" in raw_symbol:
            exchange, symbol = raw_symbol.split(":", 1)
        else:
            exchange = self.default_exchange
            symbol = raw_symbol

        # Parse quantity and price
        try:
            qty = float(str(intent.quantity))
        except (ValueError, TypeError):
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=f"Invalid intent quantity: {intent.quantity}",
            )

        price = 0.0
        if intent.price:
            raw_price = getattr(intent.price, "amount", intent.price)
            try:
                price = float(str(raw_price))
            except (ValueError, TypeError):
                price = 0.0

        # Construct Fincept UnifiedOrder
        order = self._fn.trading.UnifiedOrder()
        order.symbol = symbol
        order.exchange = exchange
        order.quantity = qty
        order.price = price

        side_str = str(intent.side).upper()
        if side_str == "BUY":
            order.side = self._fn.trading.OrderSide.Buy
        else:
            order.side = self._fn.trading.OrderSide.Sell

        type_str = str(getattr(intent, "order_type", "MARKET")).upper()
        if "LIMIT" in type_str:
            order.order_type = self._fn.trading.OrderType.Limit
        elif "STOP_LOSS" in type_str:
            order.order_type = self._fn.trading.OrderType.StopLoss
        else:
            order.order_type = self._fn.trading.OrderType.Market

        # Route order via Fincept's UnifiedTrading
        try:
            resp = self._fn.trading.place_order(self.account_id, order)
            
            client_oid = str(intent.client_order_id) if intent.client_order_id else str(uuid.uuid4())
            broker_oid = resp.order_id if resp.order_id else client_oid

            self._orders[client_oid] = {
                "broker_order_id": broker_oid,
                "instrument_id": raw_symbol,
                "side": side_str,
                "quantity": str(qty),
                "price": str(price) if price > 0 else None,
                "status": "Filled" if resp.success else "Rejected",
                "message": resp.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            return BrokerOrderAcknowledgement(
                accepted=resp.success,
                broker_order_id=BrokerOrderId(id=broker_oid),
                rejection_reason=None if resp.success else resp.message,
                fill_price=str(price) if resp.success and price > 0 else None,
                fill_quantity=str(qty) if resp.success else None,
                order_status="Filled" if resp.success else "Rejected",
            )
        except Exception as e:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=f"Exception in fincept_native.trading.place_order: {e}",
            )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        """Cancel an open order via Fincept."""
        if not self._connected or self._fn is None:
            return CancellationAcknowledgement(accepted=False, broker_order_id=order_id)

        try:
            resp = self._fn.trading.cancel_order(self.account_id, order_id.id)
            return CancellationAcknowledgement(accepted=resp.success, broker_order_id=order_id)
        except Exception:
            return CancellationAcknowledgement(accepted=False, broker_order_id=order_id)

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        """Query open positions from Fincept PaperTrading or Broker positions."""
        if not self._connected or self._fn is None:
            return BrokerPositionSnapshot(
                account_id=account_id,
                positions=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        positions_list: list[BrokerPosition] = []
        try:
            # Query paper trading positions for the portfolio/account
            raw_positions = self._fn.paper_trading.pt_get_positions(account_id)
            for p in raw_positions:
                qty = int(abs(float(p.quantity)))
                if qty == 0:
                    continue
                side = "BUY" if float(p.quantity) > 0 or p.side.lower() == "long" else "SELL"
                positions_list.append(
                    BrokerPosition(
                        instrument_id=p.symbol,
                        side=side,
                        quantity=qty,
                    )
                )
        except Exception:
            pass

        return BrokerPositionSnapshot(
            account_id=account_id,
            positions=positions_list,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        """Query portfolio balance and purchasing power from Fincept."""
        curr = self.currency
        default_cash = Money("100000.00", curr)
        if not self._connected or self._fn is None:
            return BrokerBalanceSnapshot(
                account_id=account_id,
                currency=curr,
                cash=default_cash,
                portfolio_value=default_cash,
                buying_power=default_cash,
                equity=default_cash,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            port = self._fn.paper_trading.pt_get_portfolio(account_id)
            bal = Money(f"{float(port.balance):.2f}", port.currency if port.currency else curr)
            return BrokerBalanceSnapshot(
                account_id=account_id,
                currency=port.currency if port.currency else curr,
                cash=bal,
                portfolio_value=bal,
                buying_power=bal,
                equity=bal,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            return BrokerBalanceSnapshot(
                account_id=account_id,
                currency=curr,
                cash=default_cash,
                portfolio_value=default_cash,
                buying_power=default_cash,
                equity=default_cash,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def tick(self, order_id: str) -> Optional[BrokerOrderStatus]:
        """Poll latest status for a client order."""
        info = self._orders.get(order_id)
        if not info:
            return None

        return BrokerOrderStatus(
            order_id=BrokerOrderId(id=info["broker_order_id"]),
            instrument_id=info["instrument_id"],
            side=info["side"],
            quantity=info["quantity"],
            filled_quantity=info["quantity"] if info["status"] == "Filled" else "0",
            price=info["price"],
            status=info["status"],
            created_at=info["created_at"],
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
