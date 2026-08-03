"""Tests for US equities market calendar."""

from datetime import date

from titan.data.calendar import (
    is_trading_day,
    previous_trading_day,
    next_trading_day,
    trading_days_between,
    known_holidays,
    is_early_close,
)


class TestKnownHolidays:
    def test_new_years_2026(self):
        """Jan 1, 2026 (Thu) is a holiday."""
        assert date(2026, 1, 1) in known_holidays(2026)

    def test_independence_day_observed_2026(self):
        """Jul 4, 2026 is Saturday — observed Jul 3."""
        assert date(2026, 7, 4) not in known_holidays(2026)
        assert date(2026, 7, 3) in known_holidays(2026)

    def test_christmas_2026(self):
        """Dec 25, 2026 (Fri) is a holiday."""
        assert date(2026, 12, 25) in known_holidays(2026)

    def test_mlk_day_2026(self):
        """MLK Day 2026 is Jan 19 (3rd Mon)."""
        assert date(2026, 1, 19) in known_holidays(2026)

    def test_thanksgiving_2026(self):
        """Thanksgiving 2026 is Nov 26 (4th Thu)."""
        assert date(2026, 11, 26) in known_holidays(2026)

    def test_holiday_count(self):
        """9 known holidays in 2026."""
        assert len(known_holidays(2026)) == 9


class TestIsTradingDay:
    def test_weekday_default(self):
        assert not is_trading_day(date(2026, 7, 11))
        assert not is_trading_day(date(2026, 7, 12))
        assert is_trading_day(date(2026, 7, 13))
        assert is_trading_day(date(2026, 7, 14))
        assert is_trading_day(date(2026, 7, 15))
        assert is_trading_day(date(2026, 7, 16))
        assert is_trading_day(date(2026, 7, 17))

    def test_holiday_is_not_trading(self):
        assert not is_trading_day(date(2026, 1, 1))
        assert not is_trading_day(date(2026, 7, 3))

    def test_monday_after_holiday_is_trading(self):
        assert is_trading_day(date(2026, 7, 6))

    def test_friday_before_holiday_weekend_is_trading(self):
        assert is_trading_day(date(2026, 7, 2))

    def test_christmas_eve_is_trading(self):
        assert is_trading_day(date(2026, 12, 24))


class TestPreviousTradingDay:
    def test_mid_week(self):
        assert previous_trading_day(date(2026, 7, 15)) == date(2026, 7, 14)

    def test_monday_returns_friday(self):
        assert previous_trading_day(date(2026, 7, 13)) == date(2026, 7, 10)

    def test_after_holiday(self):
        assert previous_trading_day(date(2026, 7, 6)) == date(2026, 7, 2)

    def test_after_new_year(self):
        assert previous_trading_day(date(2026, 1, 2)) == date(2025, 12, 31)


class TestNextTradingDay:
    def test_mid_week(self):
        assert next_trading_day(date(2026, 7, 14)) == date(2026, 7, 15)

    def test_friday_returns_monday(self):
        assert next_trading_day(date(2026, 7, 10)) == date(2026, 7, 13)

    def test_before_holiday(self):
        assert next_trading_day(date(2026, 7, 2)) == date(2026, 7, 6)

    def test_end_of_year(self):
        assert next_trading_day(date(2025, 12, 31)) == date(2026, 1, 2)


class TestTradingDaysBetween:
    def test_same_day(self):
        days = trading_days_between(date(2026, 7, 14), date(2026, 7, 14))
        assert days == [date(2026, 7, 14)]

    def test_one_week(self):
        days = trading_days_between(date(2026, 7, 13), date(2026, 7, 17))
        assert len(days) == 5
        assert days[0] == date(2026, 7, 13)
        assert days[-1] == date(2026, 7, 17)

    def test_weekend_skipped(self):
        days = trading_days_between(date(2026, 7, 10), date(2026, 7, 13))
        assert days == [date(2026, 7, 10), date(2026, 7, 13)]


class TestEarlyClose:
    def test_known_early_closes(self):
        assert is_early_close(date(2026, 11, 27))
        assert is_early_close(date(2026, 12, 24))

    def test_normal_day_not_early_close(self):
        assert not is_early_close(date(2026, 7, 14))
