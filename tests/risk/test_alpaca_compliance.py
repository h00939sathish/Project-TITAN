"""Unit and compliance test suite for AlpacaComplianceGate."""

from decimal import Decimal
import pytest

from titan.risk.alpaca_compliance import (
    AlpacaAccountTier,
    AlpacaComplianceConfig,
    AlpacaComplianceGate,
)


class MockClock:
    def __init__(self, start_time: float = 100000.0):
        self.current_time = start_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float):
        self.current_time += seconds


def test_account_tier_classification():
    gate = AlpacaComplianceGate()

    # Under $26,250 -> Restricted (PDT cliff safety buffer)
    assert gate.get_account_tier(Decimal("24999.00")) == AlpacaAccountTier.RESTRICTED
    assert gate.get_account_tier(Decimal("26249.99")) == AlpacaAccountTier.RESTRICTED

    # Between $26,250 and $30,000 -> Long-Only / Hedged
    assert gate.get_account_tier(Decimal("26250.00")) == AlpacaAccountTier.LONG_ONLY_HEDGED
    assert gate.get_account_tier(Decimal("29999.00")) == AlpacaAccountTier.LONG_ONLY_HEDGED

    # >= $30,000 -> Full Long/Short
    assert gate.get_account_tier(Decimal("30000.00")) == AlpacaAccountTier.FULL_LONG_SHORT
    assert gate.get_account_tier(Decimal("100000.00")) == AlpacaAccountTier.FULL_LONG_SHORT


def test_entry_rejected_when_equity_restricted():
    gate = AlpacaComplianceGate()
    ok, reason = gate.validate_entry(
        symbol="AAPL",
        side="buy",
        shares=10,
        notional_usd=Decimal("1500.00"),
        current_equity=Decimal("25500.00"), # below $26,250
    )
    assert not ok
    assert "PDT threshold" in reason


def test_short_rejected_when_tier_is_long_only():
    gate = AlpacaComplianceGate()
    ok, reason = gate.validate_entry(
        symbol="AMC",
        side="sell_short",
        shares=100,
        notional_usd=Decimal("500.00"),
        current_equity=Decimal("28000.00"), # Long-Only tier (< $30,000)
        is_etb=True,
    )
    assert not ok
    assert "below Long/Short threshold" in reason


def test_short_etb_validation():
    gate = AlpacaComplianceGate()
    equity = Decimal("50000.00")

    # ETB True -> Authorized
    ok, reason = gate.validate_entry(
        symbol="MSFT",
        side="short",
        shares=50,
        notional_usd=Decimal("15000.00"),
        current_equity=equity,
        is_etb=True,
    )
    assert ok
    assert reason == "AUTHORIZED"

    # ETB False (Hard to Borrow) -> Rejected
    ok, reason = gate.validate_entry(
        symbol="GME",
        side="short",
        shares=50,
        notional_usd=Decimal("1000.00"),
        current_equity=equity,
        is_etb=False,
    )
    assert not ok
    assert "Hard-To-Borrow" in reason

    # Locate query error / None -> Fail-closed rejection
    ok, reason = gate.validate_entry(
        symbol="XYZ",
        side="short",
        shares=10,
        notional_usd=Decimal("500.00"),
        current_equity=equity,
        is_etb=None,
    )
    assert not ok
    assert "Fail-closed on short intent" in reason


def test_auction_cross_order_rejection():
    gate = AlpacaComplianceGate()
    equity = Decimal("50000.00")

    # Time-in-force opg (Market on Open) -> Rejected
    ok, reason = gate.validate_entry(
        symbol="NVDA",
        side="buy",
        shares=10,
        notional_usd=Decimal("1200.00"),
        current_equity=equity,
        time_in_force="opg",
    )
    assert not ok
    assert "auction orders are prohibited" in reason


def test_holding_period_floor_prevents_day_trade():
    clock = MockClock(start_time=10000.0)
    gate = AlpacaComplianceGate(clock=clock)

    entry_time = clock.current_time

    # Attempt exit after 2 hours (intraday) -> REJECTED
    clock.advance(2 * 3600.0)
    ok, reason = gate.validate_exit("AAPL", entry_timestamp=entry_time)
    assert not ok
    assert "Day trade blocked under FINRA PDT rules" in reason

    # Attempt exit after 25 hours (overnight hold) -> AUTHORIZED
    clock.advance(23 * 3600.0)
    ok, reason = gate.validate_exit("AAPL", entry_timestamp=entry_time)
    assert ok
    assert reason == "AUTHORIZED"

    # Emergency killswitch override permits immediate exit
    early_exit_time = clock.current_time
    ok, reason = gate.validate_exit("AAPL", entry_timestamp=early_exit_time, is_emergency_killswitch=True)
    assert ok
    assert "Emergency kill-switch override" in reason


def test_fill_to_cancel_surveillance_defense():
    gate = AlpacaComplianceGate()
    equity = Decimal("50000.00")

    # Simulate 10 orders with only 2 fills and 8 cancellations (20% fill ratio < 70% threshold)
    for _ in range(10):
        gate.validate_entry("SPY", "buy", 1, Decimal("500.00"), equity)

    for _ in range(2):
        gate.record_fill()
    for _ in range(8):
        gate.record_cancellation()

    assert gate.metrics.fill_to_cancel_ratio == pytest.approx(0.20)

    # 11th order should be blocked due to poor fill ratio triggering surveillance defense
    ok, reason = gate.validate_entry("SPY", "buy", 1, Decimal("500.00"), equity)
    assert not ok
    assert "below Alpaca surveillance floor" in reason
