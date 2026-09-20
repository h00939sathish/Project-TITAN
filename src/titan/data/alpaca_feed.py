"""Live daily bar feed from Alpaca's StockHistoricalDataClient."""

import os
from datetime import datetime, timedelta, timezone, date
from dataclasses import dataclass
from typing import Optional

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from titan.data.approved import DataSourceError
from titan.data.normalize import ALLOWED_SYMBOLS


@dataclass
class AlpacaBar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class AlpacaDataFeed:
    """Fetch daily and intraday bars from Alpaca's data API.

    Reads credentials from the same environment variables as AlpacaAdapter
    (APCA_API_KEY_ID, APCA_API_SECRET_KEY). Paper or live data endpoint
    is determined by the ``paper`` flag.
    """

    def __init__(self, paper: bool = True):
        api_key = os.environ.get("APCA_API_KEY_ID", "")
        secret_key = os.environ.get("APCA_API_SECRET_KEY", "")
        if not api_key or not secret_key:
            raise DataSourceError(
                "Alpaca credentials not configured. "
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY."
            )
        self._client = StockHistoricalDataClient(api_key, secret_key, raw_data=False)

    def fetch_daily_bars(
        self,
        symbol: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        limit: int = 1000,
    ) -> list[AlpacaBar]:
        """Fetch daily bars for *symbol* from Alpaca.

        Returns bars sorted chronologically (oldest first).
        """
        if symbol not in ALLOWED_SYMBOLS:
            raise DataSourceError(
                f"Symbol '{symbol}' is not in ALLOWED_SYMBOLS: {sorted(ALLOWED_SYMBOLS)}"
            )

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=limit,
            adjustment="all",
        )
        bar_set = self._client.get_stock_bars(req)
        raw = bar_set.data.get(symbol, [])
        bars: list[AlpacaBar] = []
        for b in raw:
            ts = b.timestamp
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                ts_str = str(ts)
            bars.append(AlpacaBar(
                symbol=symbol,
                timestamp=ts_str,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume),
            ))
        bars.sort(key=lambda x: x.timestamp)
        return bars

    def fetch_intraday_bars(
        self,
        symbol: str,
        start: Optional[datetime | date] = None,
        end: Optional[datetime | date] = None,
        timeframe_minutes: int = 5,
        limit: int = 10000,
    ) -> list[AlpacaBar]:
        """Fetch intraday N-minute bars for *symbol* from Alpaca."""
        if symbol not in ALLOWED_SYMBOLS:
            raise DataSourceError(
                f"Symbol '{symbol}' is not in ALLOWED_SYMBOLS: {sorted(ALLOWED_SYMBOLS)}"
            )

        tf = TimeFrame.Minute if timeframe_minutes == 1 else TimeFrame(timeframe_minutes, TimeFrameUnit.Minute)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
            adjustment="all",
        )
        bar_set = self._client.get_stock_bars(req)
        raw = bar_set.data.get(symbol, [])
        bars: list[AlpacaBar] = []
        for b in raw:
            ts = b.timestamp
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                ts_str = str(ts)
            bars.append(AlpacaBar(
                symbol=symbol,
                timestamp=ts_str,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=float(b.volume),
            ))
        bars.sort(key=lambda x: x.timestamp)
        return bars

    def fetch_to_approved(self, symbol: str, days: int = 500) -> list[dict]:
        """Fetch daily bars and return as a list of dicts compatible with load_approved output."""
        end = date.today()
        start = end - timedelta(days=days)
        raw = self.fetch_daily_bars(symbol, start=start, limit=days)
        return [b.to_dict() for b in raw]
