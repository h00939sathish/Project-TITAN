"""Unit tests for Sleeve D: Indian Equities systematic engine."""

import json
from unittest.mock import MagicMock, patch
import pytest

from titan.tournament.india_sleeve import IndiaSleeveEngine, DEFAULT_INDIA_CAPITAL_INR
from titan.data.india_feed import IndianStockQuote


def test_statutory_friction_math():
    engine = IndiaSleeveEngine()
    # For a buy notional of 10,000 INR:
    # STT: 10,000 * 0.001 = 10.0
    # Stamp duty: 10,000 * 0.00015 = 1.5
    # Exchange turnover: 10,000 * 0.0000325 = 0.325
    # SEBI: 10,000 * 0.000001 = 0.01
    # GST: (0.325 + 0.01) * 0.18 = 0.0603
    # Slippage: 10,000 * 0.0002 = 2.0
    # Total = 10.0 + 1.5 + 0.325 + 0.01 + 0.0603 + 2.0 = 13.8953 -> 13.90
    friction = engine._calculate_statutory_friction(10_000.0, is_buy=True)
    assert 13.80 <= friction <= 14.00

    # Sell does not incur stamp duty
    friction_sell = engine._calculate_statutory_friction(10_000.0, is_buy=False)
    assert friction_sell < friction


def test_sleeve_evaluation_with_mock_quotes(tmp_path):
    state_file = tmp_path / "test_india_state.json"
    state_file.write_text(json.dumps({
        "cash_inr": 40_000.0,
        "cumulative_fees_inr": 100.0,
        "positions": {
            "HDFCBANK.NS": {"qty": 20, "entry_price": 800.0, "side": "LONG"},
            "SBIN.NS": {"qty": 10, "entry_price": 1000.0, "side": "LONG"},
        }
    }), encoding="utf-8")

    engine = IndiaSleeveEngine(allocated_capital_inr=100_000.0, state_file=state_file)

    mock_quotes = {
        "HDFCBANK.NS": IndianStockQuote(
            symbol="HDFCBANK.NS", display_name="HDFCBANK", price_inr=850.0,
            previous_close_inr=800.0, change_inr=50.0, change_pct=6.25,
            high_inr=860.0, low_inr=790.0, volume=100000, timestamp_utc="2026-11-21T00:00:00Z"
        ),
        "SBIN.NS": IndianStockQuote(
            symbol="SBIN.NS", display_name="SBIN", price_inr=1100.0,
            previous_close_inr=1000.0, change_inr=100.0, change_pct=10.0,
            high_inr=1120.0, low_inr=990.0, volume=50000, timestamp_utc="2026-11-21T00:00:00Z"
        ),
    }

    with patch.object(engine.feed, "fetch_universe", return_value=mock_quotes):
        tel = engine.evaluate_sleeve()

        # Total market value: (20 * 850) + (10 * 1100) = 17,000 + 11,000 = 28,000
        # Total equity: 40,000 + 28,000 = 68,000
        assert tel.allocated_capital_inr == 100_000.0
        assert tel.total_equity_inr == 68_000.0
        assert tel.cash_inr == 40_000.0
        assert tel.positions_count == 2
        # Unrealized PnL: (20 * 50) + (10 * 100) = 1,000 + 1,000 = 2,000
        assert tel.unrealized_pnl_inr == 2000.0
