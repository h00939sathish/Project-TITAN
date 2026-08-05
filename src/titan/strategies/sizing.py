"""ATR-based position sizing — volatility-adjusted share count."""

import statistics


def atr(closes: list[float], period: int = 14) -> float:
    """Compute Average Dollar Range (volatility proxy) over close prices."""
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
