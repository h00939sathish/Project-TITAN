"""Unit tests for the PEAD + Quality factor engine."""

import numpy as np
import pandas as pd
import pytest

from titan.research.pead_factor import (
    TIER_1_MIN_CAPITAL,
    calculate_pead_factor,
    calculate_quality_lowbeta_factor,
    composite_alpha_scores,
    generate_target_weights,
)


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=100, freq="B")
    symbols = [f"SYM_{i:02d}" for i in range(10)]
    np.random.seed(42)
    daily_rets = np.random.normal(0.0005, 0.015, size=(100, 10))
    prices = 100.0 * np.exp(np.cumsum(daily_rets, axis=0))
    return pd.DataFrame(prices, index=dates, columns=symbols)


@pytest.fixture
def sample_events() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "symbol": "SYM_00",
            "effective_trade_date": "2023-01-16",
            "sue_price_deflated": 0.08,
        },
        {
            "symbol": "SYM_01",
            "effective_trade_date": "2023-01-16",
            "sue_price_deflated": -0.06,
        },
        {
            "symbol": "SYM_02",
            "effective_trade_date": "2023-01-16",
            "sue_price_deflated": 0.04,
        },
        {
            "symbol": "SYM_03",
            "effective_trade_date": "2023-01-16",
            "sue_price_deflated": -0.05,
        },
    ])


def test_calculate_pead_factor_with_events(sample_prices: pd.DataFrame, sample_events: pd.DataFrame):
    scores = calculate_pead_factor(sample_prices, sample_events, holding_days=20)
    assert scores.shape == sample_prices.shape
    assert (scores.index == sample_prices.index).all()

    # Prior to event date (2023-01-16), scores should be zero
    pre_event = scores.loc[:"2023-01-13"]
    assert (pre_event == 0.0).all().all()

    # After event date, SYM_00 (highest positive surprise) should score higher than SYM_01 (negative surprise)
    post_event = scores.loc["2023-01-17"]
    assert post_event["SYM_00"] > post_event["SYM_01"]


def test_calculate_pead_factor_fallback_without_events(sample_prices: pd.DataFrame):
    scores = calculate_pead_factor(sample_prices, events_df=None, event_freq_days=20, vol_window=20)
    assert scores.shape == sample_prices.shape
    assert (scores.index == sample_prices.index).all()


def test_composite_alpha_scores(sample_prices: pd.DataFrame):
    pead = calculate_pead_factor(sample_prices, events_df=None, event_freq_days=20, vol_window=20)
    qual = calculate_quality_lowbeta_factor(sample_prices, vol_window=20, quality_lookback=40, skip=5)

    composite = composite_alpha_scores(pead, qual, weight_pead=0.5, weight_quality=0.5)
    assert composite.shape == sample_prices.shape


def test_generate_target_weights_tier_1_dollar_neutral():
    scores = pd.Series({
        "AAPL": 2.5,
        "MSFT": 1.8,
        "NVDA": 1.2,
        "GOOGL": 0.5,
        "AMZN": 0.1,
        "XOM": -0.2,
        "CVX": -0.8,
        "BA": -1.5,
        "INTC": -2.0,
        "F": -2.8,
    })

    # Capital = $35,000 (Tier 1 >= $30k)
    portfolio = generate_target_weights(
        scores_slice=scores,
        capital_usd=35000.0,
        top_k=2,
        bottom_k=2,
        gross_exposure=1.0,
    )

    assert portfolio.tier == 1
    # Longs: AAPL, MSFT (+0.25 each = +0.50)
    assert "AAPL" in portfolio.long_symbols
    assert "MSFT" in portfolio.long_symbols
    assert pytest.approx(portfolio.weights["AAPL"], 1e-4) == 0.25
    assert pytest.approx(portfolio.weights["MSFT"], 1e-4) == 0.25

    # Shorts: INTC, F (-0.25 each = -0.50)
    assert "INTC" in portfolio.short_symbols
    assert "F" in portfolio.short_symbols
    assert pytest.approx(portfolio.weights["INTC"], 1e-4) == -0.25
    assert pytest.approx(portfolio.weights["F"], 1e-4) == -0.25

    # Net exposure must be 0.0 (dollar-neutral)
    assert pytest.approx(portfolio.net_exposure, 1e-4) == 0.0
    # Gross exposure must be 1.0
    assert pytest.approx(portfolio.gross_exposure, 1e-4) == 1.0


def test_generate_target_weights_tier_2_long_only():
    scores = pd.Series({
        "AAPL": 2.5,
        "MSFT": 1.8,
        "NVDA": 1.2,
        "GOOGL": 0.5,
        "AMZN": 0.1,
        "XOM": -0.2,
        "CVX": -0.8,
        "BA": -1.5,
        "INTC": -2.0,
        "F": -2.8,
    })

    # Capital = $15,000 (Tier 2 < $30k)
    portfolio = generate_target_weights(
        scores_slice=scores,
        capital_usd=15000.0,
        top_k=2,
        bottom_k=2,
        gross_exposure=1.0,
    )

    assert portfolio.tier == 2
    # Longs: AAPL, MSFT (+0.50 each = +1.0)
    assert "AAPL" in portfolio.long_symbols
    assert "MSFT" in portfolio.long_symbols
    assert pytest.approx(portfolio.weights["AAPL"], 1e-4) == 0.50
    assert pytest.approx(portfolio.weights["MSFT"], 1e-4) == 0.50

    # Strictly ZERO shorts in Tier 2
    assert len(portfolio.short_symbols) == 0
    assert pytest.approx(portfolio.net_exposure, 1e-4) == 1.0
    assert pytest.approx(portfolio.gross_exposure, 1e-4) == 1.0


def test_generate_target_weights_etb_filter():
    scores = pd.Series({
        "AAPL": 2.5,
        "MSFT": 1.8,
        "NVDA": 1.2,
        "INTC": -2.0,
        "HTB_STOCK": -3.5, # Worst score, but NOT on ETB list
        "F": -2.8,
    })

    # Only INTC and F are ETB
    etb_whitelist = ["AAPL", "MSFT", "NVDA", "INTC", "F"]

    portfolio = generate_target_weights(
        scores_slice=scores,
        capital_usd=50000.0,
        etb_symbols=etb_whitelist,
        top_k=2,
        bottom_k=2,
        gross_exposure=1.0,
    )

    # HTB_STOCK must NOT be shorted
    assert "HTB_STOCK" not in portfolio.short_symbols
    assert "HTB_STOCK" not in portfolio.weights
    assert "F" in portfolio.short_symbols
    assert "INTC" in portfolio.short_symbols
