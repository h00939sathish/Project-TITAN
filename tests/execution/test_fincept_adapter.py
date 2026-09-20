"""Tests for FinceptBrokerAdapter (Fincept Terminal <-> Project TITAN bridge)."""

import uuid
import pytest
from dataclasses import dataclass
from typing import Optional

from titan._core import ApprovedOrderIntent
from titan.execution import (
    AdapterError,
    AdapterSessionState,
    BrokerOrderId,
    FinceptBrokerAdapter,
)


def make_approved_intent(
    instrument_id: str,
    side: str,
    quantity: str,
    order_type: str = "MARKET",
    price: Optional[str] = None,
    client_order_id: Optional[str] = None,
) -> ApprovedOrderIntent:
    return ApprovedOrderIntent(
        risk_decision_id=str(uuid.uuid4()),
        intent_id=str(uuid.uuid4()),
        client_order_id=client_order_id or str(uuid.uuid4()),
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        order_type=order_type,
        time_in_force="DAY",
        risk_profile_version="v1.0",
        price=price,
    )


class MockOrderSide:
    Buy = "Buy"
    Sell = "Sell"


class MockOrderType:
    Market = "Market"
    Limit = "Limit"
    StopLoss = "StopLoss"


@dataclass
class MockUnifiedOrder:
    symbol: str = ""
    exchange: str = ""
    quantity: float = 0.0
    price: float = 0.0
    side: str = ""
    order_type: str = ""


@dataclass
class MockOrderResponse:
    success: bool
    order_id: str
    message: str


@dataclass
class MockPtPosition:
    symbol: str
    side: str
    quantity: float


@dataclass
class MockPtPortfolio:
    balance: float
    currency: str


class MockTradingModule:
    OrderSide = MockOrderSide
    OrderType = MockOrderType
    UnifiedOrder = MockUnifiedOrder

    def __init__(self):
        self.last_placed_order: Optional[MockUnifiedOrder] = None
        self.last_account_id: Optional[str] = None
        self.cancelled_order_id: Optional[str] = None

    def place_order(self, account_id: str, order: MockUnifiedOrder) -> MockOrderResponse:
        self.last_account_id = account_id
        self.last_placed_order = order
        return MockOrderResponse(success=True, order_id="ord-fincept-999", message="Order filled")

    def cancel_order(self, account_id: str, order_id: str) -> MockOrderResponse:
        self.last_account_id = account_id
        self.cancelled_order_id = order_id
        return MockOrderResponse(success=True, order_id=order_id, message="Order cancelled")


class MockPaperTradingModule:
    def __init__(self):
        self.positions = [
            MockPtPosition(symbol="INFY", side="long", quantity=25.0),
            MockPtPosition(symbol="RELIANCE", side="short", quantity=-10.0),
        ]
        self.portfolio = MockPtPortfolio(balance=125000.50, currency="INR")

    def pt_get_positions(self, account_id: str):
        return self.positions

    def pt_get_portfolio(self, account_id: str):
        return self.portfolio


class MockRuntimeModule:
    def __init__(self, embedded: bool = True):
        self._embedded = embedded

    def health(self):
        return {"embedded": self._embedded, "application_build_id": "v4.1.0"}


class MockFinceptNative:
    def __init__(self, embedded: bool = True):
        self.runtime = MockRuntimeModule(embedded=embedded)
        self.trading = MockTradingModule()
        self.paper_trading = MockPaperTradingModule()


@pytest.fixture
def mock_fn():
    return MockFinceptNative(embedded=True)


@pytest.fixture
def adapter(mock_fn):
    return FinceptBrokerAdapter(
        account_id="paper-algo-1",
        default_exchange="NSE",
        currency="INR",
        native_module=mock_fn,
    )


def test_auth_and_heartbeat(adapter):
    session = adapter.authenticate()
    assert session.state == AdapterSessionState.CONNECTED
    assert "fincept-paper-algo-1-" in session.session_id

    hb = adapter.heartbeat()
    assert hb.connected is True
    assert hb.session_state == AdapterSessionState.CONNECTED


def test_auth_fails_when_not_embedded():
    unhealthy_fn = MockFinceptNative(embedded=False)
    bad_adapter = FinceptBrokerAdapter(native_module=unhealthy_fn)
    with pytest.raises(AdapterError) as exc:
        bad_adapter.authenticate()
    assert "embedded=False" in str(exc.value)


def test_auth_fails_without_native_module():
    bad_adapter = FinceptBrokerAdapter(native_module=None)
    bad_adapter._fn = None
    with pytest.raises(AdapterError) as exc:
        bad_adapter.authenticate()
    assert "fincept_native module not found" in str(exc.value)


def test_place_order_conversion(adapter, mock_fn):
    adapter.authenticate()

    intent = make_approved_intent(
        instrument_id="BSE:TCS",
        side="BUY",
        quantity="50",
        order_type="LIMIT",
        price="3800.50",
        client_order_id="client-intent-001",
    )

    ack = adapter.place_order(intent)

    assert ack.accepted is True
    assert ack.broker_order_id is not None
    assert ack.broker_order_id.id == "ord-fincept-999"
    assert ack.order_status == "Filled"

    # Verify Fincept UnifiedOrder was mapped accurately
    placed = mock_fn.trading.last_placed_order
    assert placed is not None
    assert placed.symbol == "TCS"
    assert placed.exchange == "BSE"
    assert placed.quantity == 50.0
    assert placed.price == 3800.50
    assert placed.side == MockOrderSide.Buy
    assert placed.order_type == MockOrderType.Limit
    assert mock_fn.trading.last_account_id == "paper-algo-1"


def test_place_order_default_exchange(adapter, mock_fn):
    adapter.authenticate()

    intent = make_approved_intent(
        instrument_id="NIFTY",
        side="SELL",
        quantity="25",
        order_type="MARKET",
        price=None,
        client_order_id="client-intent-002",
    )

    ack = adapter.place_order(intent)
    assert ack.accepted is True

    placed = mock_fn.trading.last_placed_order
    assert placed is not None
    assert placed.symbol == "NIFTY"
    assert placed.exchange == "NSE"  # Default exchange
    assert placed.side == MockOrderSide.Sell
    assert placed.order_type == MockOrderType.Market


def test_cancel_order(adapter, mock_fn):
    adapter.authenticate()
    cancel_ack = adapter.cancel(BrokerOrderId("ord-fincept-999"))
    assert cancel_ack.accepted is True
    assert cancel_ack.broker_order_id.id == "ord-fincept-999"
    assert mock_fn.trading.cancelled_order_id == "ord-fincept-999"


def test_positions_mapping(adapter):
    adapter.authenticate()
    snapshot = adapter.positions("paper-algo-1")

    assert snapshot.account_id == "paper-algo-1"
    assert len(snapshot.positions) == 2

    p1 = snapshot.positions[0]
    assert p1.instrument_id == "INFY"
    assert p1.side == "BUY"
    assert p1.quantity == 25

    p2 = snapshot.positions[1]
    assert p2.instrument_id == "RELIANCE"
    assert p2.side == "SELL"
    assert p2.quantity == 10


def test_holdings_mapping(adapter):
    adapter.authenticate()
    snapshot = adapter.holdings("paper-algo-1")

    assert snapshot.account_id == "paper-algo-1"
    assert snapshot.currency == "INR"
    assert snapshot.cash.amount == "125000.50"
    assert snapshot.cash.currency == "INR"


def test_tick_polling(adapter):
    adapter.authenticate()

    intent = make_approved_intent(
        instrument_id="NSE:SBIN",
        side="BUY",
        quantity="100",
        order_type="LIMIT",
        price="800.00",
        client_order_id="poll-intent-101",
    )
    adapter.place_order(intent)

    status = adapter.tick("poll-intent-101")
    assert status is not None
    assert status.order_id.id == "ord-fincept-999"
    assert status.instrument_id == "NSE:SBIN"
    assert status.side == "BUY"
    assert status.status == "Filled"
    assert status.quantity == "100.0"


def test_paper_trading_engine_with_fincept_adapter(mock_fn):
    from datetime import datetime, timezone
    from titan._core import RiskConfig, ReconciliationConfig, Money, TradeIntent
    from titan.execution import PaperConfig, PaperTradingEngine
    from titan.data.feed_health import FeedHealthVerdict

    adapter = FinceptBrokerAdapter(
        account_id="paper-algo-1",
        default_exchange="NSE",
        currency="INR",
        native_module=mock_fn,
    )
    risk_config = RiskConfig(
        ["INFY", "TCS"],
        Money("50000", "INR"), 1000, 5000,
        Money("100000", "INR"), 0.10, Money("5000", "INR"), 5000, 100,
    )
    config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="INR",
        starting_capital="100000",
        account_id="paper-algo-1",
        state_path="",
    )
    now = datetime.now(timezone.utc).isoformat()

    engine = PaperTradingEngine(
        config,
        adapter,
        feed_health=lambda: FeedHealthVerdict(True, "", {}, now),
    )
    from titan._core import Instrument, InstrumentId, ContractType
    from fixtures.session_init import initialize_fresh
    
    inst = Instrument(
        InstrumentId("INFY", "NSE"),
        tick_size="0.05",
        step_size=1,
        multiplier="1",
        contract_type=ContractType.Stock,
        currency="INR",
        precision=2,
    )
    engine.register_instrument(inst, instrument_id="INFY")
    initialize_fresh(engine)
    engine.start()

    assert adapter._connected is True

    intent = TradeIntent(
        strategy_id="strat-1",
        strategy_package_digest="sha256-abc",
        account_id="paper-algo-1",
        instrument_id="INFY",
        side="BUY",
        quantity="10",
        order_type="LIMIT",
        time_in_force="DAY",
        risk_profile_version="v1.0",
        market_data_timestamp=now,
        price="1500.00",
    )
    result = engine.submit_intent(intent)
    assert result.accepted is True
    assert mock_fn.trading.last_placed_order is not None
    assert mock_fn.trading.last_placed_order.symbol == "INFY"
    assert mock_fn.trading.last_placed_order.quantity == 10.0

    engine.stop()

