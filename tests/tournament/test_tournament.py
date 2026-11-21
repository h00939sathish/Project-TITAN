"""Unit tests for TITAN Multi-Asset Tournament System."""

import pandas as pd
import pytest

from titan.tournament.crypto_sleeve import CryptoSleeveEngine
from titan.tournament.options_sleeve import OptionsSleeveEngine
from titan.tournament.tournament_manager import TournamentManager


def test_crypto_sleeve_bullish_and_bearish_signals():
    engine = CryptoSleeveEngine(allocated_capital_usd=25000.0, fast_window=5, slow_window=10)

    # Bullish series (upward trend)
    bull_prices = pd.Series([100.0 + i * 2.0 for i in range(25)])
    sig_bull = engine.compute_signal("BTC/USD", bull_prices)
    assert sig_bull.trend_state == "BULLISH_TREND"
    assert sig_bull.target_weight > 0.0

    # Bearish series (downward trend)
    bear_prices = pd.Series([100.0 - i * 2.0 for i in range(25)])
    sig_bear = engine.compute_signal("BTC/USD", bear_prices)
    assert sig_bear.trend_state == "BEARISH_TREND"
    assert sig_bear.target_weight == 0.0


def test_crypto_sleeve_evaluation_orders():
    engine = CryptoSleeveEngine(allocated_capital_usd=25000.0, fast_window=5, slow_window=10)
    prices_map = {
        "BTC/USD": pd.Series([50000.0 + i * 500.0 for i in range(20)]),
        "ETH/USD": pd.Series([3000.0 + i * 20.0 for i in range(20)]),
    }

    res = engine.evaluate_sleeve(
        prices_map=prices_map,
        current_positions={"BTC/USD": 0.0, "ETH/USD": 0.0},
        total_account_equity=100000.0,
    )

    assert res["sleeve_name"] == "crypto_24_7"
    assert len(res["delta_orders"]) > 0
    for order in res["delta_orders"]:
        assert order["side"] == "buy"
        assert order["estimated_fee_usd"] > 0.0


def test_options_sleeve_spread_construction():
    engine = OptionsSleeveEngine(allocated_capital_usd=15000.0, max_collateral_per_trade=750.0)

    spread = engine.construct_bull_put_spread(
        underlying_price=600.0,
        underlying_symbol="SPY",
        spread_width=5.0,
        expiration_date="2026-12-18",
    )

    assert spread.strategy_type == "BULL_PUT_SPREAD"
    assert spread.underlying == "SPY"
    assert spread.short_strike > spread.long_strike
    assert spread.short_strike < 600.0
    assert spread.target_credit_usd > 0.0
    assert spread.max_loss_usd <= 750.0
    assert spread.contract_fees_usd > 0.0


def test_tournament_manager_multi_sleeve_evaluation():
    manager = TournamentManager(
        total_account_capital=100000.0,
        equity_budget=60000.0,
        crypto_budget=25000.0,
        options_budget=15000.0,
    )

    crypto_prices = {
        "BTC/USD": pd.Series([60000.0 + i * 500.0 for i in range(20)]),
        "ETH/USD": pd.Series([3500.0 + i * 30.0 for i in range(20)]),
        "SOL/USD": pd.Series([180.0 + i * 2.0 for i in range(20)]),
    }

    eval_res = manager.evaluate_tournament(
        account_equity=100991.0,
        equity_summary={"total_equity": 60500.0, "unrealized_pnl": 500.0, "orders_count": 10},
        crypto_prices=crypto_prices,
        crypto_positions={"BTC/USD": 0.0},
        options_positions={},
        current_market_prices={"SPY": 588.0},
    )

    sleeves = eval_res["sleeves"]
    assert "equities" in sleeves
    assert "crypto" in sleeves
    assert "options" in sleeves

    assert sleeves["equities"].target_capital_usd == 60000.0
    assert sleeves["crypto"].target_capital_usd == 25000.0
    assert sleeves["options"].target_capital_usd == 15000.0
