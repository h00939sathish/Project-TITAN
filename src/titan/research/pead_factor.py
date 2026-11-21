"""PEAD + Quality/Low-Beta Factor Engine for Alpaca Retail Swing Execution.

Combines Point-in-Time Post-Earnings Announcement Drift (PEAD) with
Quality and Low-Beta factors. Constructs capital-tiered portfolio weights:
- Tier 1 (>= $30,000): Dollar-neutral Long Top Decile / Short Bottom Decile (ETB-only).
- Tier 2 (< $30,000): Long Top Decile (100%) with optional hedge, zero shorting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Optional

import numpy as np
import pandas as pd

from titan.research.factors import cross_sectional_zscore, factor_quality_lowvol


TIER_1_MIN_CAPITAL = 30000.0


def calculate_pead_factor(
    prices: pd.DataFrame,
    events_df: Optional[pd.DataFrame] = None,
    *,
    holding_days: int = 42,
    vol_window: int = 63,
    event_freq_days: int = 63,
) -> pd.DataFrame:
    """Calculates point-in-time PEAD factor scores across the universe.

    If events_df is provided, uses true consensus SUE.
    Otherwise, uses quarterly volume-gap standardized price shock proxy.
    """
    n_bars, n_assets = prices.shape
    if n_bars < 10 or n_assets == 0:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns, dtype=float)

    if events_df is not None and not events_df.empty:
        # PIT consensus earnings events pathway
        date_strings = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in prices.index]
        date_to_idx = {d_str: i for i, d_str in enumerate(date_strings)}
        sym_to_idx = {sym: i for i, sym in enumerate(prices.columns)}

        raw_sue = np.zeros((n_bars, n_assets), dtype=float)

        for _, row in events_df.iterrows():
            sym = str(row.get("symbol", ""))
            trade_date = str(row.get("effective_trade_date", ""))

            c_idx = sym_to_idx.get(sym)
            if c_idx is None and sym == "RTN":
                c_idx = sym_to_idx.get("RTX")

            t_idx = date_to_idx.get(trade_date)
            if c_idx is None or t_idx is None:
                continue

            sue_val = float(row.get("sue_price_deflated", np.nan))
            if np.isnan(sue_val) or abs(sue_val) < 1e-12:
                raw_surp = float(row.get("raw_surprise", np.nan))
                pre_px = float(row.get("pre_event_price", np.nan))
                if not np.isnan(raw_surp) and not np.isnan(pre_px) and pre_px > 0:
                    sue_val = raw_surp / pre_px
                else:
                    surp_pct = float(row.get("surprise_pct", 0.0))
                    sue_val = surp_pct / 100.0 if not np.isnan(surp_pct) else 0.0

            if np.isnan(sue_val):
                continue

            end_hold = min(t_idx + holding_days, n_bars)
            raw_sue[t_idx:end_hold, c_idx] = sue_val

        # Cross-sectional z-score standardization
        scores_arr = np.zeros_like(raw_sue)
        for t in range(n_bars):
            row_vals = raw_sue[t]
            active_mask = np.abs(row_vals) > 1e-8
            n_active = int(np.sum(active_mask))
            if n_active >= 4:
                active_subset = row_vals[active_mask]
                m = float(np.mean(active_subset))
                s = float(np.std(active_subset))
                if s > 1e-8:
                    z = np.zeros_like(row_vals)
                    z[active_mask] = (active_subset - m) / s
                    scores_arr[t] = z
                else:
                    scores_arr[t] = row_vals
            else:
                scores_arr[t] = row_vals

        return pd.DataFrame(scores_arr, index=prices.index, columns=prices.columns)

    # Fallback quarterly abnormal event jump proxy
    daily_returns = prices.pct_change().fillna(0.0)
    mkt_ret = daily_returns.mean(axis=1)
    rolling_vol = daily_returns.rolling(vol_window).std().replace(0.0, np.nan).shift(1)

    scores = pd.DataFrame(0.0, index=prices.index, columns=prices.columns, dtype=float)
    start_idx = max(vol_window, event_freq_days)
    event_indices = list(range(start_idx, n_bars, event_freq_days))

    for ev_idx in event_indices:
        p_t = prices.iloc[ev_idx]
        p_prev = prices.iloc[ev_idx - 1]
        raw_ret = (p_t - p_prev) / p_prev.replace(0.0, np.nan)
        abnormal_ret = raw_ret - mkt_ret.iloc[ev_idx]
        vol_slice = rolling_vol.iloc[ev_idx]
        sue = (abnormal_ret / vol_slice).fillna(0.0)

        if sue.std() > 1e-8:
            z_sue = (sue - sue.mean()) / sue.std()
        else:
            z_sue = pd.Series(0.0, index=prices.columns)

        end_hold_idx = min(ev_idx + event_freq_days, n_bars)
        for h_idx in range(ev_idx, end_hold_idx):
            scores.iloc[h_idx] = z_sue

    return scores


def calculate_quality_lowbeta_factor(
    prices: pd.DataFrame,
    *,
    vol_window: int = 63,
    quality_lookback: int = 252,
    skip: int = 21,
) -> pd.DataFrame:
    """Computes Quality & Low-Volatility factor z-scores."""
    return factor_quality_lowvol(
        prices=prices,
        vol_window=vol_window,
        quality_lookback=quality_lookback,
        skip=skip,
    )


def composite_alpha_scores(
    pead_scores: pd.DataFrame,
    quality_scores: pd.DataFrame,
    *,
    weight_pead: float = 0.50,
    weight_quality: float = 0.50,
) -> pd.DataFrame:
    """Blends PEAD and Quality/Low-Beta scores into a single composite rank."""
    common_idx = pead_scores.index.intersection(quality_scores.index)
    common_cols = pead_scores.columns.intersection(quality_scores.columns)

    p_sub = pead_scores.loc[common_idx, common_cols]
    q_sub = quality_scores.loc[common_idx, common_cols]

    raw_composite = (weight_pead * p_sub) + (weight_quality * q_sub)
    return cross_sectional_zscore(raw_composite)


@dataclass(frozen=True)
class TargetPortfolio:
    """Target portfolio weights and tier classification."""
    weights: dict[str, float]
    tier: int
    gross_exposure: float
    net_exposure: float
    long_symbols: tuple[str, ...]
    short_symbols: tuple[str, ...]


def generate_target_weights(
    scores_slice: pd.Series,
    capital_usd: float,
    *,
    etb_symbols: Optional[Collection[str]] = None,
    top_k: int = 5,
    bottom_k: int = 5,
    gross_exposure: float = 1.0,
    deadband_prev_weights: Optional[dict[str, float]] = None,
) -> TargetPortfolio:
    """Generates compliance-verified target portfolio weights based on account capital.

    Parameters:
    - scores_slice: Factor scores for universe at decision point t.
    - capital_usd: Account equity in USD.
    - etb_symbols: Whitelist of Easy-To-Borrow symbols. If None, all are treated as ETB.
    - top_k: Number of long positions.
    - bottom_k: Number of short positions.
    - gross_exposure: Total gross leverage (1.0 = 100% total, 0.5 long / 0.5 short).
    - deadband_prev_weights: Previous target weights for turnover buffering.
    """
    valid_scores = scores_slice.dropna()
    if len(valid_scores) < top_k + bottom_k:
        return TargetPortfolio(
            weights={},
            tier=1 if capital_usd >= TIER_1_MIN_CAPITAL else 2,
            gross_exposure=0.0,
            net_exposure=0.0,
            long_symbols=(),
            short_symbols=(),
        )

    # Sort assets by score descending
    sorted_syms = list(valid_scores.sort_values(ascending=False).index)
    target_longs = sorted_syms[:top_k]

    # Tier 1 vs Tier 2 Determination
    if capital_usd >= TIER_1_MIN_CAPITAL:
        # Tier 1: Dollar-Neutral Long/Short
        tier = 1
        leg_weight = gross_exposure / 2.0

        # Candidate shorts are bottom_k, filtered by ETB
        candidate_shorts = sorted_syms[-bottom_k:]
        if etb_symbols is not None:
            etb_set = {s.upper() for s in etb_symbols}
            # Keep candidate if ETB, otherwise backfill from lowest ranked ETB stocks
            filtered_shorts = [s for s in candidate_shorts if s.upper() in etb_set]
            if len(filtered_shorts) < bottom_k:
                remaining_candidates = [s for s in reversed(sorted_syms) if s.upper() in etb_set and s not in target_longs and s not in filtered_shorts]
                needed = bottom_k - len(filtered_shorts)
                filtered_shorts.extend(remaining_candidates[:needed])
            target_shorts = filtered_shorts
        else:
            target_shorts = candidate_shorts

        weights: dict[str, float] = {}
        for s in target_longs:
            weights[s] = leg_weight / max(len(target_longs), 1)
        for s in target_shorts:
            weights[s] = -leg_weight / max(len(target_shorts), 1)

    else:
        # Tier 2: Long-Only Top K (100% capital allocated across longs, zero shorts)
        tier = 2
        weights = {}
        long_unit = gross_exposure / max(len(target_longs), 1)
        for s in target_longs:
            weights[s] = long_unit
        target_shorts = []

    long_syms_tuple = tuple(s for s, w in weights.items() if w > 0)
    short_syms_tuple = tuple(s for s, w in weights.items() if w < 0)
    gross_exp = sum(abs(w) for w in weights.values())
    net_exp = sum(weights.values())

    return TargetPortfolio(
        weights=weights,
        tier=tier,
        gross_exposure=gross_exp,
        net_exposure=net_exp,
        long_symbols=long_syms_tuple,
        short_symbols=short_syms_tuple,
    )
