"""Feature registrations for the first experiment.

Registers features at import time so they're discoverable, versioned,
and linked to their compute functions.
"""
from titan.research.feature import register_feature, Feature
from titan.research.features import (
    compute_atr_percentile,
    compute_relative_strength,
    compute_return,
    compute_forward_return,
    compute_volatility_contraction_flag,
    compute_realized_volatility,
)

# ── Market Structure ──────────────────────────────────────────────────────

register_feature(Feature(
    id="forward_return_20d",
    category="market_structure",
    inputs=("close",),
    frequency="1D",
    version=1,
    description="20-trading-day forward return",
    min_history=0,
    compute_fn=lambda rows: compute_forward_return(rows, 20),
))

register_feature(Feature(
    id="return_60d",
    category="market_structure",
    inputs=("close",),
    frequency="1D",
    version=1,
    description="60-trading-day trailing return",
    min_history=60,
    compute_fn=lambda rows: compute_return(rows, 60),
))

# ── Volatility ────────────────────────────────────────────────────────────

register_feature(Feature(
    id="atr_percentile_20",
    category="volatility",
    inputs=("high", "low", "close"),
    frequency="1D",
    version=1,
    description="20-day ATR ranked against 252-day lookback (0-1)",
    min_history=252,
    compute_fn=lambda rows: compute_atr_percentile(rows, 14, 252),
))

register_feature(Feature(
    id="realized_vol_20",
    category="volatility",
    inputs=("close",),
    frequency="1D",
    version=1,
    description="20-day realized vol (std dev of log returns)",
    min_history=20,
    compute_fn=lambda rows: compute_realized_volatility(rows, 20),
))

register_feature(Feature(
    id="vol_contraction_flag",
    category="volatility",
    inputs=("high", "low", "close"),
    frequency="1D",
    version=1,
    description="True when ATR percentile < 20% (volatility contraction)",
    min_history=252,
    compute_fn=lambda rows: compute_volatility_contraction_flag(
        compute_atr_percentile(rows, 14, 252), 0.20
    ),
))

# ── Relative Strength ─────────────────────────────────────────────────────

register_feature(Feature(
    id="relative_strength_60d",
    category="relative_strength",
    inputs=("close",),
    frequency="1D",
    version=1,
    description="SPY 60d return minus benchmark (QQQ) 60d return",
    min_history=60,
    # NB: requires benchmark data passed at compute time
    compute_fn=None,  # handled specially
))
