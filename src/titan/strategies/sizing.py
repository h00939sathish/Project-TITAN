import math
from typing import Optional
from dataclasses import dataclass

@dataclass
class SizingResult:
    quantity: int
    is_tradable: bool
    reason: str = ""

class Sizer:
    @staticmethod
    def size(
        equity: float,
        notional_allocation_pct: float,
        price: float,
        conversion_rate: Optional[float],
        conversion_timestamp: Optional[str],
        step_size: int,
        minimum_quantity: int,
        now_timestamp: Optional[str] = None,
        data_freshness_threshold_ms: int = 5000
    ) -> SizingResult:
        
        if conversion_timestamp and now_timestamp:
            from datetime import datetime
            try:
                # Handle potential timezone offsets or Z
                t_conv = datetime.fromisoformat(conversion_timestamp.replace('Z', '+00:00'))
                t_now = datetime.fromisoformat(now_timestamp.replace('Z', '+00:00'))
                delta_ms = (t_now - t_conv).total_seconds() * 1000
                if delta_ms > data_freshness_threshold_ms:
                    return SizingResult(0, False, f"Market data is stale (delta {delta_ms}ms > {data_freshness_threshold_ms}ms)")
            except ValueError:
                pass # Fallback if invalid timestamps
        
        if conversion_rate is None or conversion_rate <= 0:
            return SizingResult(0, False, "Sizing conversion data missing")
            
        if equity <= 0 or notional_allocation_pct <= 0 or price <= 0:
            return SizingResult(0, False, "Invalid equity, allocation, or price")
            
        notional_base = equity * (notional_allocation_pct / 100.0)
        notional_target = notional_base * conversion_rate
        
        raw_shares = notional_target / price
        
        # Round down to step_size
        rounded_shares = math.floor(raw_shares / step_size) * step_size
        
        if rounded_shares < minimum_quantity:
            return SizingResult(0, False, "Allocation cannot fund minimum lot")
            
        return SizingResult(int(rounded_shares), True)


# ---------------------------------------------------------------------------
# DEPRECATED (ADR-028 migration in progress): legacy ATR-based sizing kept as
# compat shims for callers not yet migrated to the canonical Sizer
# (src/titan/strategies/pipeline.py, scripts/ensemble_lab.py,
# tests/strategies/test_phases_2_9.py). Migration to Sizer is P1
# economic-parity work (titan_alpha_loop_FINAL.md §2). Do NOT use in new code.
# ---------------------------------------------------------------------------

import statistics


def atr(closes: list[float], period: int = 14) -> float:
    """Compute Average Dollar Range (volatility proxy) over close prices.

    DEPRECATED: legacy ATR sizing helper; keep until callers migrate to Sizer.
    """
    if len(closes) < period + 1:
        return 0.0
    returns = [
        abs(closes[i] - closes[i - 1])
        for i in range(-period, 0)
    ]
    return statistics.mean(returns) if returns else 0.0


def position_size(
    equity: float,
    closes: list[float],
    risk_per_trade_pct: float = 0.5,
    atr_period: int = 14,
    stop_atr_multiple: float = 2.0,
    min_shares: int = 1,
    max_shares: int = 1000,
) -> int:
    """Compute position size = risk_budget / (atr * stop_multiple * price).

    DEPRECATED: legacy ATR sizing helper; keep until callers migrate to Sizer.

    Args:
        equity: Current account equity (cash + position value).
        closes: Recent close prices for ATR calculation.
        risk_per_trade_pct: Fraction of equity to risk per trade (e.g. 0.5 = 0.5%).
        atr_period: Lookback for ATR.
        stop_atr_multiple: Stop distance as multiple of ATR.
        min_shares: Minimum position size.
        max_shares: Maximum position size.

    Returns:
        Number of shares/units.
    """
    if not closes or len(closes) < atr_period + 1:
        return min_shares
    price = closes[-1]
    if price <= 0:
        return min_shares
    risk_budget = equity * (risk_per_trade_pct / 100.0)
    vol = atr(closes, atr_period)
    if vol < 1e-10:
        return min_shares
    stop_distance = vol * stop_atr_multiple
    shares = int(risk_budget / stop_distance)
    return max(min_shares, min(shares, max_shares))
