"""Unit tests for the Alpaca daily rebalance orchestrator."""

from decimal import Decimal
import numpy as np
import pandas as pd
import pytest

from titan.operations.daily_rebalance import DailyRebalanceOrchestrator
from titan.risk.alpaca_compliance import AlpacaComplianceGate


@pytest.fixture
def mock_market():
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "XOM", "INTC", "F"]
    np.random.seed(42)
    daily_rets = np.random.normal(0.0005, 0.015, size=(100, len(symbols)))
    prices = 100.0 * np.exp(np.cumsum(daily_rets, axis=0))
    prices_df = pd.DataFrame(prices, index=dates, columns=symbols)

    current_prices = {sym: float(prices_df[sym].iloc[-1]) for sym in symbols}
    return prices_df, current_prices


class MockBrokerClient:
    def __init__(self):
        self.dispatched = []

    def place_order(self, intent):
        self.dispatched.append(intent)


def test_rebalance_aborts_below_pdt_buffer(mock_market):
    prices_df, current_prices = mock_market
    orchestrator = DailyRebalanceOrchestrator(pacing_delay_seconds=0.0)

    # Capital is $25,000 (below $26,250 safety buffer)
    summary = orchestrator.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=25000.0,
    )

    assert not summary.compliance_approved
    assert summary.orders_dispatched == 0
    assert any("PDT buffer" in r for r in summary.rejection_reasons)


def test_tier_1_rebalance_success(mock_market):
    prices_df, current_prices = mock_market
    client = MockBrokerClient()

    gate = AlpacaComplianceGate()
    orchestrator = DailyRebalanceOrchestrator(
        compliance_gate=gate,
        broker_client=client,
        pacing_delay_seconds=0.0,
    )

    # Capital is $35,000 (Tier 1 >= $30k)
    summary = orchestrator.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=35000.0,
        etb_symbols=["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "XOM", "INTC", "F"],
        top_k=2,
        bottom_k=2,
    )

    assert summary.compliance_approved
    assert summary.tier == 1
    assert summary.orders_dispatched == 4  # 2 longs + 2 shorts
    assert summary.orders_rejected == 0
    assert len(client.dispatched) == 4

    # Verify both buys and shorts exist
    sides = [o.side for o in client.dispatched]
    assert "buy" in sides
    assert "short" in sides


def test_tier_2_rebalance_success_long_only(mock_market):
    prices_df, current_prices = mock_market
    client = MockBrokerClient()

    gate = AlpacaComplianceGate()
    orchestrator = DailyRebalanceOrchestrator(
        compliance_gate=gate,
        broker_client=client,
        pacing_delay_seconds=0.0,
    )

    # Capital is $28,000 (Tier 2: above $26,250 PDT buffer, below $30,000 Tier 1)
    summary = orchestrator.execute_daily_cycle(
        prices_df=prices_df,
        current_positions={},
        current_prices=current_prices,
        account_equity=28000.0,
        top_k=2,
        bottom_k=2,
    )

    assert summary.compliance_approved
    assert summary.tier == 2
    assert summary.orders_dispatched == 2  # 2 longs only
    assert summary.orders_rejected == 0
    assert len(client.dispatched) == 2

    # Strictly NO short orders
    sides = [o.side for o in client.dispatched]
    assert all(s == "buy" for s in sides)
