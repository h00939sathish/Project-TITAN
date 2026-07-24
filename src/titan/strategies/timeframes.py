from datetime import timedelta
from enum import StrEnum


class UnsupportedTimeframeError(ValueError):
    pass


class Timeframe(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"

    @classmethod
    def from_duration(cls, duration: timedelta) -> "Timeframe":
        mapping = {
            timedelta(minutes=1): cls.ONE_MINUTE,
            timedelta(minutes=5): cls.FIVE_MINUTES,
            timedelta(minutes=15): cls.FIFTEEN_MINUTES,
            timedelta(hours=1): cls.ONE_HOUR,
            timedelta(days=1): cls.ONE_DAY,
        }
        try:
            return mapping[duration]
        except KeyError as error:
            raise UnsupportedTimeframeError(
                f"unsupported bar duration: {duration}"
            ) from error
