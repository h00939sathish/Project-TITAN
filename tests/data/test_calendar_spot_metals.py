from datetime import date

from titan.data.calendar_spot_metals import (
    is_spot_metal_trading_day,
    next_spot_metal_trading_day,
    previous_spot_metal_trading_day,
)


def test_spot_gold_weekday_is_trading():
    assert is_spot_metal_trading_day(date(2026, 7, 20))  # Monday


def test_spot_gold_weekend_not_trading():
    assert not is_spot_metal_trading_day(date(2026, 7, 18))  # Saturday
    assert not is_spot_metal_trading_day(date(2026, 7, 19))  # Sunday


def test_spot_gold_previous_trading_day_skip_weekend():
    mon = date(2026, 7, 20)
    fri = date(2026, 7, 17)
    assert previous_spot_metal_trading_day(mon) == fri


def test_spot_gold_next_trading_day_skip_weekend():
    fri = date(2026, 7, 17)
    mon = date(2026, 7, 20)
    assert next_spot_metal_trading_day(fri) == mon
