"""Spot metal market calendar — weekday daily bars only.

For daily bar purposes: Mon-Fri are trading days, Sat-Sun are not.
Intraday Sunday open, Friday close, daily maintenance breaks, and
venue holidays are not modeled. Intraday trading is unsupported.
"""

from datetime import date, timedelta


def is_spot_metal_trading_day(d: date) -> bool:
    return d.weekday() < 5


def previous_spot_metal_trading_day(d: date) -> date:
    candidate = d - timedelta(days=1)
    while not is_spot_metal_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_spot_metal_trading_day(d: date) -> date:
    candidate = d + timedelta(days=1)
    while not is_spot_metal_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
