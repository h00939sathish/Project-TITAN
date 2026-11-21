"""Unit tests for AlpacaBatchDispatcher."""

from decimal import Decimal
import pytest

from titan.risk.alpaca_compliance import AlpacaComplianceGate
from titan.execution.alpaca_batch import (
    AlpacaBatchDispatcher,
    BatchOrderIntent,
    BatchExecutionReceipt,
)


class MockSleepTracker:
    def __init__(self):
        self.sleep_calls: list[float] = []

    def __call__(self, seconds: float):
        self.sleep_calls.append(seconds)


def test_compute_target_deltas():
    gate = AlpacaComplianceGate()
    dispatcher = AlpacaBatchDispatcher(compliance_gate=gate)

    equity = Decimal("100000.00")
    # Target: 10% AAPL ($10k), 10% MSFT ($10k), -10% TSLA (-$10k short)
    target_weights = {"AAPL": 0.10, "MSFT": 0.10, "TSLA": -0.10}
    current_prices = {"AAPL": 200.0, "MSFT": 400.0, "TSLA": 250.0}
    current_positions = {"AAPL": 20, "MSFT": 25, "TSLA": 0} # held: AAPL 20 shares ($4k), MSFT 25 shares ($10k)

    intents = dispatcher.compute_target_deltas(
        target_weights=target_weights,
        current_prices=current_prices,
        total_equity=equity,
        current_positions=current_positions,
    )

    intents_by_sym = {i.symbol: i for i in intents}

    # AAPL target: $10,000 / $200 = 50 shares. Current = 20. Delta = +30 (Buy 30)
    assert "AAPL" in intents_by_sym
    assert intents_by_sym["AAPL"].side == "buy"
    assert intents_by_sym["AAPL"].shares == 30
    assert intents_by_sym["AAPL"].notional_usd == Decimal("6000.00")

    # MSFT target: $10,000 / $400 = 25 shares. Current = 25. Delta = 0 (No order)
    assert "MSFT" not in intents_by_sym

    # TSLA target: -$10,000 / $250 = -40 shares. Current = 0. Delta = -40 (Short 40)
    assert "TSLA" in intents_by_sym
    assert intents_by_sym["TSLA"].side == "short"
    assert intents_by_sym["TSLA"].shares == 40
    assert intents_by_sym["TSLA"].notional_usd == Decimal("10000.00")


def test_paced_rebalance_execution():
    gate = AlpacaComplianceGate()
    sleep_tracker = MockSleepTracker()
    dispatcher = AlpacaBatchDispatcher(
        compliance_gate=gate,
        pacing_delay_seconds=0.10,
        sleep_fn=sleep_tracker,
    )

    equity = Decimal("50000.00")
    target_weights = {"AAPL": 0.20, "GOOGL": 0.20}
    current_prices = {"AAPL": 200.0, "GOOGL": 100.0}
    current_positions = {"AAPL": 0, "GOOGL": 0}

    receipt = dispatcher.execute_rebalance(
        target_weights=target_weights,
        current_prices=current_prices,
        total_equity=equity,
        current_positions=current_positions,
    )

    assert receipt.orders_authorized == 2
    assert receipt.orders_dispatched == 2
    assert receipt.orders_rejected == 0
    assert receipt.account_tier == "FULL_LONG_SHORT"

    # Verifies pacing sleep was called between orders
    assert len(sleep_tracker.sleep_calls) == 2
    assert sleep_tracker.sleep_calls == [0.10, 0.10]


def test_rebalance_respects_etb_rejections():
    gate = AlpacaComplianceGate()
    dispatcher = AlpacaBatchDispatcher(compliance_gate=gate, pacing_delay_seconds=0.0)

    equity = Decimal("50000.00")
    # Target shorting an HTB stock (GME) and an ETB stock (AAPL)
    target_weights = {"AAPL": -0.10, "GME": -0.10}
    current_prices = {"AAPL": 100.0, "GME": 20.0}
    current_positions = {"AAPL": 0, "GME": 0}
    etb_status = {"AAPL": True, "GME": False} # GME is Hard-to-Borrow

    receipt = dispatcher.execute_rebalance(
        target_weights=target_weights,
        current_prices=current_prices,
        total_equity=equity,
        current_positions=current_positions,
        etb_status=etb_status,
    )

    assert receipt.orders_authorized == 1
    assert receipt.orders_dispatched == 1
    assert receipt.orders_rejected == 1
    assert receipt.rejections[0][0] == "GME"
    assert "Hard-To-Borrow" in receipt.rejections[0][1]


def test_rebalance_aborts_when_capital_restricted():
    gate = AlpacaComplianceGate()
    dispatcher = AlpacaBatchDispatcher(compliance_gate=gate)

    # Equity below $26,250 threshold
    low_equity = Decimal("25000.00")
    target_weights = {"AAPL": 0.10}
    current_prices = {"AAPL": 100.0}

    receipt = dispatcher.execute_rebalance(
        target_weights=target_weights,
        current_prices=current_prices,
        total_equity=low_equity,
        current_positions={},
    )

    assert receipt.account_tier == "RESTRICTED"
    assert receipt.orders_dispatched == 0
    assert receipt.rejections[0][0] == "PORTFOLIO"
