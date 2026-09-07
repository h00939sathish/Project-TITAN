"""Cross-sectional factor calculation and normalization engine.

Research-only. Computes point-in-time cross-sectional rankings and z-scores
across an aligned multi-asset price matrix.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cross_sectional_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Standardizes each cross-sectional slice (row) to mean=0, std=1."""
    mean = df.mean(axis=1)
    std = df.std(axis=1).replace(0.0, np.nan)
    zscored = df.sub(mean, axis=0).div(std, axis=0)
    return zscored.fillna(0.0)


def factor_momentum_12_1m(
    prices: pd.DataFrame,
    lookback: int = 252,
    skip: int = 21,
) -> pd.DataFrame:
    """12-1 Month Cross-Sectional Momentum.

    Computes cumulative return from (t - lookback) to (t - skip), skipping the
    most recent `skip` days to avoid short-term liquidity reversal contamination.
    """
    if len(prices) < lookback + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    p_lag = prices.shift(skip)
    p_base = prices.shift(lookback)
    raw_mom = (p_lag - p_base) / p_base
    return cross_sectional_zscore(raw_mom)


def factor_reversal_12_1m(
    prices: pd.DataFrame,
    lookback: int = 252,
    skip: int = 21,
) -> pd.DataFrame:
    """12-1 Month Cross-Sectional Reversal.

    Inverts the 12-1M relative return so that the worst historical performers
    receive the highest ranking score (Long target), and the best historical
    performers receive the lowest score (Short target).
    """
    if len(prices) < lookback + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    p_lag = prices.shift(skip)
    p_base = prices.shift(lookback)
    raw_mom = (p_lag - p_base) / p_base
    return cross_sectional_zscore(-raw_mom)


def factor_short_term_reversal(

    prices: pd.DataFrame,
    window: int = 5,
) -> pd.DataFrame:
    """Short-Term Reversal Factor (e.g. 5-day / 1-week).

    Negative of recent return: ranks oversold laggards highest and overbought
    leaders lowest to capture liquidity provision and mean-reversion premia.
    """
    if len(prices) < window + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    ret = prices.pct_change(window)
    # Invert return so lowest return gets highest score (buy laggards)
    raw_rev = -ret
    return cross_sectional_zscore(raw_rev)


def factor_low_volatility(
    prices: pd.DataFrame,
    window: int = 63,
) -> pd.DataFrame:
    """Low-Volatility Factor (Inverse Realized Volatility).

    Ranks instruments by inverse rolling standard deviation of daily returns.
    """
    if len(prices) < window + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    daily_returns = prices.pct_change().fillna(0.0)
    rolling_vol = daily_returns.rolling(window).std().replace(0.0, np.nan)
    inv_vol = 1.0 / rolling_vol
    return cross_sectional_zscore(inv_vol)


def factor_volatility_adjusted_momentum(
    prices: pd.DataFrame,
    mom_lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
) -> pd.DataFrame:
    """Sharpe / Volatility-Adjusted Momentum.

    Computes 12-1M momentum divided by rolling realized volatility.
    """
    max_lookback = max(mom_lookback, vol_window)
    if len(prices) < max_lookback + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    p_lag = prices.shift(skip)
    p_base = prices.shift(mom_lookback)
    raw_mom = (p_lag - p_base) / p_base

    daily_returns = prices.pct_change().fillna(0.0)
    rolling_vol = daily_returns.rolling(vol_window).std().replace(0.0, np.nan)

    vol_adj_mom = raw_mom / rolling_vol
    return cross_sectional_zscore(vol_adj_mom)


def factor_quality_lowvol(
    prices: pd.DataFrame,
    vol_window: int = 63,
    quality_lookback: int = 252,
    skip: int = 21,
    weight_lowvol: float = 0.5,
    weight_quality: float = 0.5,
) -> pd.DataFrame:
    """Composite Quality & Low-Volatility Factor.

    Combines inverse realized volatility (Low-Vol component) with
    risk-adjusted return consistency / rolling Sharpe proxy (Quality component).
    """
    max_lookback = max(quality_lookback, vol_window)
    if len(prices) < max_lookback + 1:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    # 1. Low-volatility score (inverse rolling standard deviation)
    daily_returns = prices.pct_change().fillna(0.0)
    rolling_vol = daily_returns.rolling(vol_window).std().replace(0.0, np.nan)
    inv_vol = 1.0 / rolling_vol
    z_lowvol = cross_sectional_zscore(inv_vol)

    # 2. Quality / Risk-adjusted return consistency score
    p_lag = prices.shift(skip)
    p_base = prices.shift(quality_lookback)
    raw_ret = (p_lag - p_base) / p_base
    quality_score = raw_ret / rolling_vol
    z_quality = cross_sectional_zscore(quality_score)

    # 3. Composite score
    composite = (weight_lowvol * z_lowvol) + (weight_quality * z_quality)
    return cross_sectional_zscore(composite)

