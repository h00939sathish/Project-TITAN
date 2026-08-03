"""Forex market calendar — 24/5 (Sun 5pm ET - Fri 5pm ET).

For daily bar purposes: Mon-Fri are trading days, Sat-Sun are not.
Individual broker holiday observances may vary — not modeled in MVP.
"""

from datetime import date, timedelta


def is_forex_trading_day(d: date) -> bool:
    return d.weekday() < 5


def previous_forex_trading_day(d: date) -> date:
    candidate = d - timedelta(days=1)
    while not is_forex_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_forex_trading_day(d: date) -> date:
    candidate = d + timedelta(days=1)
    while not is_forex_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
