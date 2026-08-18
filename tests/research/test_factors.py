"""Tests for Cross-Sectional Factor Computation Engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from titan.research.factors import (
    cross_sectional_zscore,
    factor_low_volatility,
    factor_momentum_12_1m,
    factor_short_term_reversal,
    factor_volatility_adjusted_momentum,
)


def test_cross_sectional_zscore_properties():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "A": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            "B": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0],
            "C": [3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0],
        },
        index=dates,
    )
    z = cross_sectional_zscore(df)
    # Check mean across columns is 0
    np.testing.assert_allclose(z.mean(axis=1), 0.0, atol=1e-7)
    # Check std across columns is 1
    np.testing.assert_allclose(z.std(axis=1), 1.0, atol=1e-7)
    # C should have the highest z-score, A the lowest
    assert (z["C"] > z["B"]).all()
    assert (z["B"] > z["A"]).all()


def test_momentum_12_1m_skips_recent_month():
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    # Asset A steadily grows, Asset B flat
    prices = pd.DataFrame(
        {
            "A": [100.0 * (1.001 ** i) for i in range(300)],
            "B": [100.0] * 300,
        },
        index=dates,
    )
    mom = factor_momentum_12_1m(prices, lookback=252, skip=21)
    assert len(mom) == 300
    # After warmup, A should have higher momentum score than B
    assert mom.iloc[-1]["A"] > mom.iloc[-1]["B"]


def test_short_term_reversal_inverts_recent_return():
    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    # Asset A spikes, Asset B drops
    prices = pd.DataFrame(
        {
            "A": [100.0] * 15 + [120.0] * 5,
            "B": [100.0] * 15 + [80.0] * 5,
        },
        index=dates,
    )
    rev = factor_short_term_reversal(prices, window=5)
    # Asset B (dropped) should have HIGHER reversal score (buy laggard) than Asset A
    assert rev.iloc[-1]["B"] > rev.iloc[-1]["A"]


def test_low_volatility_rewards_stable_asset():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    # Asset A: low vol (0.1% changes), Asset B: high vol (5% oscillations)
    prices = pd.DataFrame(
        {
            "A": [100.0 + (i % 2) * 0.1 for i in range(100)],
            "B": [100.0 + (i % 2) * 5.0 for i in range(100)],
        },
        index=dates,
    )
    low_vol = factor_low_volatility(prices, window=63)
    # Asset A should have higher low-vol score than Asset B
    assert low_vol.iloc[-1]["A"] > low_vol.iloc[-1]["B"]
