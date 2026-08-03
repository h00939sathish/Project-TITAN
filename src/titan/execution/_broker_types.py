from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from titan._core import BrokerPosition, Money


class AdapterSessionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    EXPIRING = "expiring"


@dataclass
class BrokerOrderId:
    id: str


@dataclass
class BrokerOrderAcknowledgement:
    accepted: bool
    broker_order_id: Optional[BrokerOrderId] = None
    rejection_reason: Optional[str] = None
    fill_price: Optional[str] = None
    fill_quantity: Optional[str] = None
    order_status: Optional[str] = None


@dataclass
class CancellationAcknowledgement:
    accepted: bool
    broker_order_id: Optional[BrokerOrderId] = None


@dataclass
class OrderAmendment:
    quantity: Optional[str] = None
    price: Optional[str] = None
    stop_price: Optional[str] = None
    time_in_force: Optional[str] = None


@dataclass
class BrokerFill:
    execution_id: str
    order_id: BrokerOrderId
    instrument_id: str
    side: str
    quantity: str
    price: str
    fees: Money
    currency: str
    timestamp: str


@dataclass
class BrokerOrderStatus:
    order_id: BrokerOrderId
    instrument_id: str
    side: str
    quantity: str
    filled_quantity: str
    price: Optional[str]
    status: str
    created_at: str
    updated_at: str


@dataclass
class BrokerPositionSnapshot:
    account_id: str
    positions: list[BrokerPosition]
    timestamp: str


@dataclass
class BrokerBalanceSnapshot:
    account_id: str
    currency: str
    cash: Money
    portfolio_value: Money
    buying_power: Money
    equity: Money
    timestamp: str


@dataclass
class QuoteSnapshot:
    instrument_id: str
    bid_price: Optional[str]
    ask_price: Optional[str]
    bid_size: Optional[str]
    ask_size: Optional[str]
    timestamp: str


@dataclass
class InstrumentSet:
    instrument_ids: list[str]


@dataclass
class QueryWindow:
    start: str
    end: str


@dataclass
class BrokerOrderSnapshot:
    account_id: str
    orders: list[BrokerOrderStatus]
    timestamp: str


@dataclass
class BrokerFillSnapshot:
    account_id: str
    fills: list[BrokerFill]
    timestamp: str


@dataclass
class AdapterHealth:
    connected: bool
    session_state: AdapterSessionState = AdapterSessionState.DISCONNECTED
    degradation: list[str] = field(default_factory=list)


@dataclass
class ReconciliationCursor:
    from_order_id: Optional[str] = None
    from_timestamp: Optional[str] = None


@dataclass
class Session:
    session_id: str
    state: AdapterSessionState
    created_at: str
    expires_at: Optional[str] = None


@dataclass
class OrderResult:
    """Result of submitting a trade intent through the engine pipeline."""
    accepted: bool
    rejection_reason: Optional[str] = None
    broker_order_id: Optional[BrokerOrderId] = None
    fills: list[BrokerFill] = field(default_factory=list)
    position: Optional[object] = None
    cash_balance: Optional[object] = None


class AdapterError(Exception):
    def __init__(self, message: str, classification: str):
        self.message = message
        self.classification = classification
        super().__init__(f"[{classification}] {message}")
