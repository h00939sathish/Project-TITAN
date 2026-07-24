"""Tests for strategy timeframe qualification."""

import titan.strategies.registrations  # noqa: F401 — triggers registration
from titan.strategies.registry import get_registry
from titan.strategies.timeframes import Timeframe


def test_daily_ma_is_not_implicitly_intraday_qualified():
    registration = get_registry().get("ma-crossover")
    assert registration.is_qualified_for(Timeframe.ONE_DAY, {"fast": 5, "slow": 20})
    assert not registration.is_qualified_for(Timeframe.FIVE_MINUTES, {"fast": 3, "slow": 10})
