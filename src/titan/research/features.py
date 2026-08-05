"""Feature compute functions for the feature registry.

Each function takes a list of dicts (rows with OHLCV columns) and
returns a list of float values aligned to the input rows.
"""
from __future__ import annotations

import statistics
from collections import deque


def compute_ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average."""
    result: list[float | None] = []
    multiplier = 2.0 / (period + 1)
    ema: float | None = None
    for v in values:
        if ema is None:
            ema = v
        else:
            ema = (v - ema) * multiplier + ema
        result.append(ema)
    return result


def compute_ema_crossover_signal(
    rows: list[dict], fast: int = 5, slow: int = 20,
) -> list[str | None]:
    """Exact replica of TITAN's live MovingAverageCrossover strategy.

    Returns 'BUY' when fast EMA crosses above slow EMA,
    'SELL' when fast EMA crosses below slow EMA, None otherwise.
    Computed exactly as src/titan/strategies/moving_average.py does it.
    """
    closes = [float(r["close"]) for r in rows]
    fast_ema = compute_ema(closes, fast)
    slow_ema = compute_ema(closes, slow)

    result: list[str | None] = [None] * len(rows)
    for i in range(1, len(rows)):
        f_now = fast_ema[i]
        s_now = slow_ema[i]
        f_prev = fast_ema[i - 1]
        s_prev = slow_ema[i - 1]

        if f_now is None or s_now is None or f_prev is None or s_prev is None:
            continue

        if f_prev <= s_prev and f_now > s_now:
            result[i] = "BUY"
        elif f_prev >= s_prev and f_now < s_now:
            result[i] = "SELL"

    return result


def compute_atr(rows: list[dict], period: int = 14) -> list[float | None]:
    """Average True Range."""
    result: list[float | None] = []
    prev_close: float | None = None
    buf: deque[float] = deque(maxlen=period)

    for r in rows:
        high = float(r["high"])
        low = float(r["low"])
        close = float(r["close"])

        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))

        buf.append(tr)
        result.append(sum(buf) / len(buf) if len(buf) == period else None)
        prev_close = close

    return result


def compute_atr_percentile(rows: list[dict], atr_period: int = 14, lookback: int = 252) -> list[float | None]:
    """ATR percentile: where current ATR ranks in its lookback window (0-1)."""
    atr_values = compute_atr(rows, atr_period)
    result: list[float | None] = []
    buf: deque[float] = deque(maxlen=lookback)

    for atr in atr_values:
        if atr is None:
            result.append(None)
            continue
        buf.append(atr)
        if len(buf) < lookback:
            result.append(None)
        else:
            count_below = sum(1 for x in buf if x <= atr)
            result.append(count_below / len(buf))

    return result


def compute_forward_return(rows: list[dict], horizon: int = 20) -> list[float | None]:
    """Forward N-period return based on close prices."""
    closes = [float(r["close"]) for r in rows]
    result: list[float | None] = []
    for i in range(len(closes)):
        if i + horizon < len(closes):
            result.append((closes[i + horizon] / closes[i]) - 1.0)
        else:
            result.append(None)
    return result


def compute_return(rows: list[dict], period: int = 60) -> list[float | None]:
    """Rolling N-period return."""
    closes = [float(r["close"]) for r in rows]
    result: list[float | None] = []
    for i in range(len(closes)):
        if i >= period:
            result.append((closes[i] / closes[i - period]) - 1.0)
        else:
            result.append(None)
    return result


def compute_relative_strength(
    primary: list[dict],
    benchmark: list[dict],
    period: int = 60,
) -> list[float | None]:
    """Relative strength = primary_return - benchmark_return over period."""
    primary_ret = compute_return(primary, period)
    bm_ret = compute_return(benchmark, period)
    return [
        (p - b) if (p is not None and b is not None) else None
        for p, b in zip(primary_ret, bm_ret)
    ]


def compute_realized_volatility(rows: list[dict], period: int = 20) -> list[float | None]:
    """Realized volatility as std dev of daily log returns."""
    closes = [float(r["close"]) for r in rows]
    log_returns: list[float] = []
    for i in range(1, len(closes)):
        log_returns.append(__ln(closes[i] / closes[i - 1]))

    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period:
            result.append(None)
        else:
            chunk = log_returns[i - period:i]
            result.append(statistics.stdev(chunk))

    return result


def compute_volatility_contraction_flag(
    atr_percentile: list[float | None],
    threshold: float = 0.20,
) -> list[bool | None]:
    """True when ATR percentile is below threshold (volatility contraction)."""
    return [
        (p < threshold) if p is not None else None
        for p in atr_percentile
    ]


def __ln(x: float) -> float:
    import math
    return math.log(x)
