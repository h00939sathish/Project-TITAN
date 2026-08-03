"""US equities market calendar — known holidays, trading day calculation."""

from datetime import date, timedelta


def _nearest_weekday(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    count = 0
    d = date(year, month, 1)
    while d.month == month:
        if d.weekday() == weekday:
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)
    raise ValueError(f"Could not find {n}th weekday {weekday} in {year}-{month}")


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    while d.month == month:
        if d.weekday() == weekday:
            return d
        d -= timedelta(days=1)
    raise ValueError(f"Could not find last weekday {weekday} in {year}-{month}")


def _us_holidays(year: int) -> set[date]:
    holidays: set[date] = set()

    holidays.add(_nearest_weekday(date(year, 1, 1)))     # New Year's
    holidays.add(_nth_weekday(year, 1, 0, 3))             # MLK Day (3rd Mon)
    holidays.add(_nth_weekday(year, 2, 0, 3))             # Presidents' Day (3rd Mon)
    holidays.add(_last_weekday(year, 5, 0))               # Memorial Day (last Mon)
    holidays.add(_nearest_weekday(date(year, 6, 19)))     # Juneteenth
    holidays.add(_nearest_weekday(date(year, 7, 4)))      # Independence Day
    holidays.add(_nth_weekday(year, 9, 0, 1))             # Labor Day (1st Mon)
    holidays.add(_nth_weekday(year, 11, 3, 4))            # Thanksgiving (4th Thu)
    holidays.add(_nearest_weekday(date(year, 12, 25)))    # Christmas

    return holidays


KNOWN_HOLIDAYS_CACHE: dict[int, set[date]] = {}


def known_holidays(year: int) -> set[date]:
    if year not in KNOWN_HOLIDAYS_CACHE:
        KNOWN_HOLIDAYS_CACHE[year] = _us_holidays(year)
    return KNOWN_HOLIDAYS_CACHE[year]


_EARLY_CLOSES: set[date] = {
    date(2026, 11, 27),
    date(2026, 12, 24),
}


def is_trading_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    holidays = known_holidays(d.year)
    return d not in holidays


def previous_trading_day(d: date) -> date:
    candidate = d - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_trading_day(d: date) -> date:
    candidate = d + timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def trading_days_between(start: date, end: date) -> list[date]:
    result: list[date] = []
    d = start
    while d <= end:
        if is_trading_day(d):
            result.append(d)
        d += timedelta(days=1)
    return result


def is_early_close(d: date) -> bool:
    return d in _EARLY_CLOSES
