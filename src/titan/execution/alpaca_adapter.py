import os
import time
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest, StopLimitOrderRequest

from titan._core import ApprovedOrderIntent, BrokerPosition, Money, Side

from ._broker_adapter import BrokerAdapter
from ._broker_types import (
    AdapterError,
    AdapterHealth,
    AdapterSessionState,
    BrokerBalanceSnapshot,
    BrokerFill,
    BrokerFillSnapshot,
    BrokerOrderAcknowledgement,
    BrokerOrderId,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancellationAcknowledgement,
    InstrumentSet,
    OrderAmendment,
    QueryWindow,
    QuoteSnapshot,
    Session,
)

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"
DEFAULT_RATE_LIMIT = 200


class AlpacaAdapter(BrokerAdapter):
    """Alpaca broker adapter implementing the Broker.spec.md interface.

    Reads credentials from environment variables unless explicitly provided.
    Construction validates paper-only mode:
      - ``paper`` must be True
      - ``base_url`` must be ``https://paper-api.alpaca.markets``
      - API credentials must be non-empty
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        paper: bool = True,
    ):
        self._api_key = api_key or os.environ.get("APCA_API_KEY_ID", "")
        self._secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY", "")
        resolved_base_url = base_url or os.environ.get(
            "APCA_API_BASE_URL",
            PAPER_BASE_URL if paper else LIVE_BASE_URL,
        )

        if not paper:
            raise AdapterError(
                "Live trading is not supported. paper must be True.",
                "configuration",
            )
        if resolved_base_url != PAPER_BASE_URL:
            raise AdapterError(
                f"Live endpoint rejected. base_url must be {PAPER_BASE_URL}, got: {resolved_base_url}.",
                "configuration",
            )

        parsed = urlparse(resolved_base_url)
        if parsed.scheme != "https":
            raise AdapterError(
                f"Endpoint rejected. "
                f"API endpoint requires https scheme, got: {resolved_base_url}. ",
                "configuration",
            )
        if not self._api_key or not self._secret_key:
            raise AdapterError(
                "Alpaca API credentials not configured. "
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in environment.",
                "configuration",
            )


        self._base_url = resolved_base_url
        self._paper = paper
        self._client: Optional[TradingClient] = None
        self._session: Optional[Session] = None
        self._daily_order_count: int = 0
        self._daily_order_date: Optional[str] = None
        self._max_daily_orders: int = 20
        self._max_retries = 3
        self._retry_delay = 0.2

    def _ensure_client(self) -> TradingClient:
        if self._client is None:
            if not self._api_key or not self._secret_key:
                raise AdapterError(
                    "Alpaca API credentials not configured. "
                    "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in environment.",
                    "authentication",
                )
            self._client = TradingClient(
                self._api_key,
                self._secret_key,
                paper=self._paper,
            )
        return self._client

    def authenticate(self) -> Session:
        session_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            client = self._ensure_client()
            account = client.get_account()
            session = Session(
                session_id=session_id,
                state=AdapterSessionState.CONNECTED,
                created_at=created_at,
            )
            self._session = session
            return session
        except AdapterError:
            raise
        except Exception as e:
            session = Session(
                session_id=session_id,
                state=AdapterSessionState.DISCONNECTED,
                created_at=created_at,
            )
            self._session = session
            raise AdapterError(
                f"Authentication failed: {e}",
                "authentication",
            ) from e

    def refresh(self, session: Session) -> Session:
        return self.authenticate()

    def _map_side(self, side: str) -> OrderSide:
        s = side.strip().upper()
        if s == "BUY":
            return OrderSide.BUY
        elif s == "SELL":
            return OrderSide.SELL
        raise AdapterError(f"Unknown side: {side}", "invalid_order_parameters")

    def _map_order_type(self, order_type: str) -> OrderType:
        t = order_type.strip().upper()
        if t == "MARKET":
            return OrderType.MARKET
        elif t == "LIMIT":
            return OrderType.LIMIT
        elif t == "STOP":
            return OrderType.STOP
        elif t == "STOP_LIMIT":
            return OrderType.STOP_LIMIT
        raise AdapterError(f"Unknown order type: {order_type}", "invalid_order_parameters")

    def _map_time_in_force(self, tif: str) -> TimeInForce:
        t = tif.strip().upper()
        if t == "DAY":
            return TimeInForce.DAY
        elif t == "GTC":
            return TimeInForce.GTC
        elif t == "IOC":
            return TimeInForce.IOC
        elif t == "FOK":
            return TimeInForce.FOK
        return TimeInForce.DAY

    def _in_regular_session(self) -> bool:
        now_et = datetime.now(timezone.utc).astimezone(ZoneInfo("US/Eastern"))
        if now_et.weekday() >= 5:
            return False
        from titan.data.calendar import is_early_close, is_trading_day
        et_date = now_et.date()
        if not is_trading_day(et_date):
            return False
        et_minutes = now_et.hour * 60 + now_et.minute
        open_minutes = 9 * 60 + 30
        if is_early_close(et_date):
            return open_minutes <= et_minutes < 13 * 60
        return open_minutes <= et_minutes < 16 * 60

    def _call_with_retry(self, fn, *args, **kwargs):
        last_exc = None
        for attempt in range(self._max_retries):
            try:
                return fn(*args, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (2 ** attempt))
        raise last_exc  # type: ignore[misc]

    def _check_daily_order_limit(self) -> BrokerOrderAcknowledgement | None:
        today = datetime.now(timezone.utc).astimezone(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
        if self._daily_order_date != today:
            self._daily_order_date = today
            self._daily_order_count = 0
        if self._daily_order_count >= self._max_daily_orders:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=f"Daily order limit ({self._max_daily_orders}) reached",
            )
        return None

    def place_order(self, intent: ApprovedOrderIntent) -> BrokerOrderAcknowledgement:
        limit_check = self._check_daily_order_limit()
        if limit_check:
            return limit_check
        if not self._in_regular_session():
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason="Orders blocked outside US regular session (9:30-16:00 ET Mon-Fri)",
            )
        client = self._ensure_client()
        side = self._map_side(str(intent.side))
        qty = str(intent.quantity)
        symbol = str(intent.instrument_id)

        try:
            order_type = self._map_order_type(str(intent.order_type))
        except AdapterError as e:
            return BrokerOrderAcknowledgement(accepted=False, rejection_reason=str(e))

        tif = self._map_time_in_force(str(intent.time_in_force))

        try:
            if order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type=order_type,
                    time_in_force=tif,
                    client_order_id=str(intent.client_order_id) if intent.client_order_id else None,
                )
            elif order_type == OrderType.LIMIT:
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type=order_type,
                    time_in_force=tif,
                    limit_price=str(intent.price) if intent.price else None,
                    client_order_id=str(intent.client_order_id) if intent.client_order_id else None,
                )
            elif order_type == OrderType.STOP:
                request = StopOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type=order_type,
                    time_in_force=tif,
                    stop_price=str(intent.stop_price) if intent.stop_price else None,
                    client_order_id=str(intent.client_order_id) if intent.client_order_id else None,
                )
            elif order_type == OrderType.STOP_LIMIT:
                request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type=order_type,
                    time_in_force=tif,
                    stop_price=str(intent.stop_price) if intent.stop_price else None,
                    limit_price=str(intent.price) if intent.price else None,
                    client_order_id=str(intent.client_order_id) if intent.client_order_id else None,
                )
            else:
                return BrokerOrderAcknowledgement(
                    accepted=False,
                    rejection_reason=f"Unsupported order type: {order_type}",
                )

            alpaca_order = self._call_with_retry(client.submit_order, request)
            self._daily_order_count += 1
            broker_id = BrokerOrderId(id=str(alpaca_order.id))
            try:
                raw_fill_qty = alpaca_order.filled_qty
                raw_fill_price = alpaca_order.filled_avg_price
                has_fill = raw_fill_qty is not None and float(str(raw_fill_qty)) > 0
                fill_qty = str(raw_fill_qty) if has_fill else None
                fill_price = str(raw_fill_price) if has_fill and raw_fill_price else None
            except (ValueError, TypeError):
                fill_qty = None
                fill_price = None
            order_status = str(alpaca_order.status.value) if alpaca_order.status else None
            return BrokerOrderAcknowledgement(
                accepted=True,
                broker_order_id=broker_id,
                fill_price=fill_price,
                fill_quantity=fill_qty,
                order_status=order_status,
            )

        except APIError as e:
            err_msg = str(e)
            if "client_order_id" in err_msg or "duplicate" in err_msg.lower() or "already exists" in err_msg.lower():
                try:
                    existing = client.get_order_by_client_id(client_order_id)
                    if existing:
                        broker_id = BrokerOrderId(id=str(existing.id))
                        return BrokerOrderAcknowledgement(
                            accepted=True,
                            broker_order_id=broker_id,
                            fill_price=str(existing.filled_avg_price) if getattr(existing, 'filled_avg_price', None) else None,
                            fill_quantity=str(existing.filled_qty) if getattr(existing, 'filled_qty', None) else None,
                            order_status=str(existing.status.value) if getattr(existing, 'status', None) else None,
                        )
                except Exception:
                    pass
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=err_msg,
            )

        except (ConnectionError, TimeoutError) as e:
            raise AdapterError(f"Alpaca connection failed: {e}", "operational") from e
        except Exception as e:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=str(e),
            )

    def modify(self, order_id: BrokerOrderId, amendment: OrderAmendment) -> BrokerOrderAcknowledgement:
        client = self._ensure_client()
        try:
            alpaca_order = client.replace_order_by_id(
                order_id=order_id.id,
                qty=amendment.quantity,
                limit_price=amendment.price,
                stop_price=amendment.stop_price,
                time_in_force=amendment.time_in_force,
            )
            broker_id = BrokerOrderId(id=str(alpaca_order.id))
            return BrokerOrderAcknowledgement(accepted=True, broker_order_id=broker_id)
        except Exception as e:
            return BrokerOrderAcknowledgement(
                accepted=False,
                rejection_reason=str(e),
            )

    def cancel(self, order_id: BrokerOrderId) -> CancellationAcknowledgement:
        client = self._ensure_client()
        try:
            response = client.cancel_order_by_id(order_id.id)
            return CancellationAcknowledgement(accepted=True, broker_order_id=order_id)
        except Exception as e:
            return CancellationAcknowledgement(accepted=False, broker_order_id=order_id)

    def _map_alpaca_side(self, side: str) -> str:
        s = side.strip().lower()
        if s == "long" or s == "buy":
            return "BUY"
        elif s == "short" or s == "sell":
            return "SELL"
        return side.upper()

    def positions(self, account_id: str) -> BrokerPositionSnapshot:
        client = self._ensure_client()
        try:
            alpaca_positions = client.get_all_positions()
            positions: list[BrokerPosition] = []
            for p in alpaca_positions:
                pos_side = self._map_alpaca_side(p.side)
                qty = int(float(str(p.qty))) if p.qty else 0
                positions.append(BrokerPosition(
                    instrument_id=str(p.symbol),
                    side=pos_side,
                    quantity=qty,
                ))
            return BrokerPositionSnapshot(
                account_id=account_id,
                positions=positions,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                f"Failed to fetch positions: {e}",
                "operational",
            ) from e

    def holdings(self, account_id: str) -> BrokerBalanceSnapshot:
        client = self._ensure_client()
        try:
            account = client.get_account()
            cash_str = str(account.cash) if account.cash else "0"
            portfolio_str = str(account.portfolio_value) if account.portfolio_value else "0"
            bp_str = str(account.buying_power) if account.buying_power else "0"
            equity_str = str(account.equity) if account.equity else "0"
            currency = str(account.currency) if account.currency else "USD"

            return BrokerBalanceSnapshot(
                account_id=account_id,
                currency=currency,
                cash=Money(cash_str, currency),
                portfolio_value=Money(portfolio_str, currency),
                buying_power=Money(bp_str, currency),
                equity=Money(equity_str, currency),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                f"Failed to fetch holdings: {e}",
                "operational",
            ) from e

    def quotes(self, instruments: InstrumentSet) -> dict[str, QuoteSnapshot]:
        raise AdapterError(
            "Real-time quotes require StockHistoricalDataClient and are not yet implemented",
            "unsupported_capability",
        )

    def orders(self, account_id: str, window: QueryWindow) -> BrokerOrderSnapshot:
        client = self._ensure_client()
        try:
            alpaca_orders = client.get_orders(
                status="all",
                after=window.start if window.start else None,
                until=window.end if window.end else None,
                limit=500,
            )
            statuses: list[BrokerOrderStatus] = []
            for o in alpaca_orders:
                side = self._map_alpaca_side(str(o.side))
                statuses.append(BrokerOrderStatus(
                    order_id=BrokerOrderId(id=str(o.id)),
                    instrument_id=str(o.symbol),
                    side=side,
                    quantity=str(o.qty) if o.qty else "0",
                    filled_quantity=str(o.filled_qty) if o.filled_qty else "0",
                    price=str(o.limit_price) if o.limit_price else None,
                    status=str(o.status.value) if o.status else "unknown",
                    created_at=str(o.created_at) if o.created_at else "",
                    updated_at=str(o.updated_at) if o.updated_at else "",
                ))
            return BrokerOrderSnapshot(
                account_id=account_id,
                orders=statuses,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                f"Failed to fetch orders: {e}",
                "operational",
            ) from e

    def fills(self, account_id: str, window: QueryWindow) -> BrokerFillSnapshot:
        client = self._ensure_client()
        try:
            activities = client.get_account_activities(
                activity_type="FILL",
                date=None,
                after=window.start if window.start else None,
                until=window.end if window.end else None,
                direction="desc",
                page_size=500,
            )
            fills_list: list[BrokerFill] = []
            for a in activities:
                fills_list.append(BrokerFill(
                    execution_id=str(a.id) if a.id else str(uuid.uuid4()),
                    order_id=BrokerOrderId(id=str(a.order_id)) if a.order_id else BrokerOrderId(id="unknown"),
                    instrument_id=str(a.symbol) if a.symbol else "",
                    side=str(a.side) if a.side else "",
                    quantity=str(a.qty) if a.qty else "0",
                    price=str(a.price) if a.price else "0",
                    fees=Money(str(a.fees) if a.fees else "0", "USD"),
                    currency="USD",
                    timestamp=str(a.transaction_time) if a.transaction_time else "",
                ))
            return BrokerFillSnapshot(
                account_id=account_id,
                fills=fills_list,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except AdapterError:
            raise
        except Exception as e:
            raise AdapterError(
                f"Failed to fetch fills: {e}",
                "operational",
            ) from e

    def save_order_count_state(self) -> dict:
        return {
            "daily_order_date": self._daily_order_date,
            "daily_order_count": self._daily_order_count,
        }

    def restore_order_count_state(self, state: dict) -> None:
        self._daily_order_date = state.get("daily_order_date")
        self._daily_order_count = state.get("daily_order_count", 0)

    def tick(self, order_id: str) -> None:
        """Poll status update from Alpaca for specified order_id."""
        try:
            client = self._ensure_client()
            client.get_order_by_id(order_id)
        except Exception:
            pass
        return None

    def heartbeat(self) -> AdapterHealth:

        try:
            client = self._ensure_client()
            client.get_account()
            state = AdapterSessionState.CONNECTED
            if self._session and self._session.state == AdapterSessionState.CONNECTED:
                state = AdapterSessionState.CONNECTED
            return AdapterHealth(connected=True, session_state=state)
        except AdapterError:
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=["Credentials not configured"],
            )
        except Exception as e:
            return AdapterHealth(
                connected=False,
                session_state=AdapterSessionState.DISCONNECTED,
                degradation=[str(e)],
            )

def create_broker_paper_adapter() -> AlpacaAdapter:
    """Create a hardened AlpacaAdapter for broker-paper mode.

    Reads credentials from environment, enforces paper-only at construction,
    and raises ``AdapterError`` if anything is misconfigured before any
    network activity.
    """
    api_key = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")
    base_url = os.environ.get("APCA_API_BASE_URL")

    if not api_key or not secret_key:
        raise AdapterError(
            "broker-paper: APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in environment.",
            "configuration",
        )

    return AlpacaAdapter(
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url or PAPER_BASE_URL,
        paper=True,
    )
