"""Sleeve B: 24/7 Alpaca Crypto Trend Engine for Project TITAN Tournament.

Executes low-turnover trend-following on high-liquidity crypto assets (BTC/USD, ETH/USD, SOL/USD)
using 4-hour bars, accounting for Alpaca's 15-25 bps taker fee structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
import pandas as pd


DEFAULT_CRYPTO_CAPITAL = 25000.0
CRYPTO_SYMBOLS = ("BTC/USD", "ETH/USD", "SOL/USD")


@dataclass(frozen=True)
class CryptoSignal:
    symbol: str
    target_weight: float # e.g. +0.33 for long, 0.0 for cash/neutral
    current_price: float
    trend_state: str     # "BULLISH_TREND", "BEARISH_TREND", "NEUTRAL"
    fast_ema: float
    slow_ema: float


class CryptoSleeveEngine:
    """Computes trend signals and target weights for the 24/7 Crypto Sleeve."""

    def __init__(
        self,
        allocated_capital_usd: float = DEFAULT_CRYPTO_CAPITAL,
        fast_window: int = 12,  # 12 bars (e.g., 48 hours on 4h bars)
        slow_window: int = 48,  # 48 bars (e.g., 8 days on 4h bars)
        max_symbols: int = 3,
    ):
        self.allocated_capital_usd = allocated_capital_usd
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.max_symbols = max_symbols

    def compute_signal(self, symbol: str, prices: pd.Series) -> CryptoSignal:
        """Computes trend state and target weight for a single crypto asset."""
        if len(prices) < self.slow_window + 5:
            current_px = float(prices.iloc[-1]) if len(prices) > 0 else 0.0
            return CryptoSignal(
                symbol=symbol,
                target_weight=0.0,
                current_price=current_px,
                trend_state="NEUTRAL",
                fast_ema=0.0,
                slow_ema=0.0,
            )

        fast_ema = float(prices.ewm(span=self.fast_window, adjust=False).mean().iloc[-1])
        slow_ema = float(prices.ewm(span=self.slow_window, adjust=False).mean().iloc[-1])
        current_px = float(prices.iloc[-1])

        # Trend rule: Fast EMA > Slow EMA and Price > Slow EMA
        if fast_ema > slow_ema and current_px > slow_ema:
            trend_state = "BULLISH_TREND"
            target_weight = 1.0 / float(self.max_symbols)
        else:
            trend_state = "BEARISH_TREND"
            # Spot crypto long-only or cash to avoid funding/short fees
            target_weight = 0.0

        return CryptoSignal(
            symbol=symbol,
            target_weight=target_weight,
            current_price=current_px,
            trend_state=trend_state,
            fast_ema=fast_ema,
            slow_ema=slow_ema,
        )

    def evaluate_sleeve(
        self,
        prices_map: Mapping[str, pd.Series],
        current_positions: Mapping[str, float],
        total_account_equity: float,
    ) -> Dict[str, Any]:
        """Evaluates all target crypto assets and generates target rebalance deltas."""
        signals: Dict[str, CryptoSignal] = {}
        target_weights: Dict[str, float] = {}
        target_shares: Dict[str, float] = {}
        delta_orders: List[Dict[str, Any]] = []

        # Enforce sleeve capital ceiling
        sleeve_budget = min(self.allocated_capital_usd, total_account_equity * 0.30)

        for sym in CRYPTO_SYMBOLS:
            series = prices_map.get(sym)
            if series is None or len(series) == 0:
                continue

            sig = self.compute_signal(sym, series)
            signals[sym] = sig
            target_weights[sym] = sig.target_weight

            px = sig.current_price
            if px <= 0:
                continue

            target_dollar = sleeve_budget * sig.target_weight
            target_qty = target_dollar / px
            target_shares[sym] = target_qty

            current_qty = float(current_positions.get(sym, 0.0))
            delta_qty = target_qty - current_qty

            # Order threshold: only rebalance if delta notional > $50 (avoid micro-churn)
            delta_notional = abs(delta_qty) * px
            if delta_notional >= 50.0:
                side = "buy" if delta_qty > 0 else "sell"
                delta_orders.append({
                    "symbol": sym,
                    "side": side,
                    "qty": round(abs(delta_qty), 5),
                    "price": px,
                    "notional_usd": round(delta_notional, 2),
                    "estimated_fee_usd": round(delta_notional * 0.0025, 4), # 25 bps taker fee
                })

        return {
            "sleeve_name": "crypto_24_7",
            "sleeve_budget_usd": sleeve_budget,
            "signals": signals,
            "target_weights": target_weights,
            "delta_orders": delta_orders,
        }
