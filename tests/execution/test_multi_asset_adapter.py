"""Unit & Integration test for Multi-Asset Paper Trading (Equities, Crypto, Forex)."""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from titan._core import (
    ApprovedOrderIntent,
    ContractType,
    Instrument,
    InstrumentId,
    Money,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.execution import FinceptBrokerAdapter, PaperConfig, PaperTradingEngine
from titan.data.feed_health import FeedHealthVerdict
from fixtures.session_init import initialize_fresh


@pytest.fixture
def mock_multi_asset_fn():
    class MockOrder:
        def __init__(self):
            self.symbol = ""
            self.exchange = ""
            self.quantity = 0.0
            self.price = 0.0
            self.side = ""
            self.order_type = ""

    class MockTrading:
        class OrderSide:
            Buy = "Buy"
            Sell = "Sell"
        class OrderType:
            Market = "Market"
            Limit = "Limit"
        UnifiedOrder = MockOrder

        def __init__(self):
            self.placed_orders = []

        def place_order(self, account_id, order):
            oid = f"fc-{order.exchange}-{uuid.uuid4().hex[:6]}"
            self.placed_orders.append((account_id, order, oid))
            class Resp:
                success = True
                order_id = oid
                message = "Order Accepted"
            return Resp()

        def cancel_order(self, account_id, order_id):
            class Resp:
                success = True
            return Resp()

    class MockPaper:
        def __init__(self):
            self.portfolios = {}

        def pt_get_positions(self, account_id):
            return []

        def pt_get_portfolio(self, account_id):
            class Port:
                balance = 1000000.0
                currency = "USD"
            return Port()

    class MockNative:
        def __init__(self):
            self.runtime = type("Runtime", (), {"health": lambda s: {"embedded": True}})()
            self.trading = MockTrading()
            self.paper_trading = MockPaper()

    return MockNative()


def test_multi_asset_paper_trading_execution(mock_multi_asset_fn):
    now_str = datetime.now(timezone.utc).isoformat()

    assets = [
        ("NSE", "INR", "INFY", ContractType.Stock, "25", "1520.00", "0.05"),
        ("CRYPTO", "USD", "BTC-USD", ContractType.Crypto, "1", "64250.00", "0.50"),
        ("FX", "USD", "EURUSD", ContractType.Forex, "50000", "1.0850", "0.0001"),
    ]

    for venue, currency, symbol, contract_type, qty, price, tick_sz in assets:
        account_id = f"paper-{venue.lower()}"
        adapter = FinceptBrokerAdapter(
            account_id=account_id,
            default_exchange=venue,
            currency=currency,
            native_module=mock_multi_asset_fn,
        )
        risk_cfg = RiskConfig([symbol], Money("1000000", currency), 100000, 5000, Money("2000000", currency), 0.20, Money("100000", currency), 5000, 100)
        paper_cfg = PaperConfig(risk_config=risk_cfg, reconciliation_config=ReconciliationConfig(), currency=currency, starting_capital="1000000", account_id=account_id, state_path="")
        engine = PaperTradingEngine(paper_cfg, adapter, feed_health=lambda: FeedHealthVerdict(True, "", {}, now_str))

        inst = Instrument(
            InstrumentId(symbol, venue),
            tick_size=tick_sz,
            step_size=1,
            multiplier="1",
            contract_type=contract_type,
            currency=currency,
            precision=4,
        )
        engine.register_instrument(inst, symbol)
        initialize_fresh(engine)
        engine.start()

        intent = TradeIntent(
            strategy_id=f"strat-{venue.lower()}",
            strategy_package_digest="sha256-test",
            account_id=account_id,
            instrument_id=symbol,
            side="BUY",
            quantity=qty,
            order_type="LIMIT",
            time_in_force="DAY",
            risk_profile_version="v1.0",
            market_data_timestamp=now_str,
            price=price,
        )
        result = engine.submit_intent(intent)
        assert result.accepted is True
        engine.stop()

    assert len(mock_multi_asset_fn.trading.placed_orders) == 3
    eq_order = mock_multi_asset_fn.trading.placed_orders[0]
    crypto_order = mock_multi_asset_fn.trading.placed_orders[1]
    fx_order = mock_multi_asset_fn.trading.placed_orders[2]

    assert eq_order[1].symbol == "INFY"
    assert eq_order[1].exchange == "NSE"
    assert eq_order[1].quantity == 25.0

    assert crypto_order[1].symbol == "BTC-USD"
    assert crypto_order[1].exchange == "CRYPTO"
    assert crypto_order[1].quantity == 1.0

    assert fx_order[1].symbol == "EURUSD"
    assert fx_order[1].exchange == "FX"
    assert fx_order[1].quantity == 50000.0
