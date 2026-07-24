from datetime import timedelta

import pytest
from titan.strategies.timeframes import Timeframe, UnsupportedTimeframeError


@pytest.mark.parametrize(("duration", "expected"), [
    (timedelta(minutes=5), Timeframe.FIVE_MINUTES),
    (timedelta(minutes=15), Timeframe.FIFTEEN_MINUTES),
    (timedelta(hours=1), Timeframe.ONE_HOUR),
    (timedelta(days=1), Timeframe.ONE_DAY),
])
def test_from_duration_maps_every_subscribed_bar(duration, expected):
    assert Timeframe.from_duration(duration) is expected


def test_from_duration_rejects_unsupported_interval():
    with pytest.raises(UnsupportedTimeframeError, match="unsupported bar duration"):
        Timeframe.from_duration(timedelta(minutes=30))
