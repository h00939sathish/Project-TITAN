"""Polygon.io daily-bar fetcher for forex and spot metals.

API key from POLYGON_API_KEY env var.
Supports forex pairs (EURUSD -> C:EUR/USD) and spot gold (XAUUSD -> C:XAU/USD).
"""

import os
from datetime import date, timedelta
from urllib.request import urlopen, Request
import json

from titan.data.approved import DataSourceError


POLYGON_TICKER_MAP = {
    "EURUSD": "C:EUR/USD",
    "GBPUSD": "C:GBP/USD",
    "AUDUSD": "C:AUD/USD",
    "NZDUSD": "C:NZD/USD",
    "XAUUSD": "C:XAU/USD",
}


def _polygon_ticker(symbol: str) -> str:
    ticker = POLYGON_TICKER_MAP.get(symbol.upper())
    if ticker is None:
        raise DataSourceError(f"Symbol '{symbol}' has no Polygon ticker mapping")
    return ticker


def fetch_daily_bars(symbol: str, days: int = 500) -> list[dict]:
    """Fetch daily OHLC bars for *symbol* from Polygon.io.

    Returns list of dicts compatible with the backtest engine format.
    Returns empty list if no data.
    """
    ticker = _polygon_ticker(symbol)

    api_key = os.environ.get("POLYGON_API_KEY", "")
    if not api_key:
        raise DataSourceError("POLYGON_API_KEY not set")
    end = date.today()
    start = end - timedelta(days=days)

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/"
        f"{start.isoformat()}/{end.isoformat()}"
        f"?adjusted=true&sort=asc&limit=5000&apiKey={api_key}"
    )

    req = Request(url, headers={"User-Agent": "titan/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise DataSourceError(f"Polygon fetch failed for {symbol}: {e}")

    results = data.get("results", [])
    if not results:
        if data.get("status") == "ERROR":
            raise DataSourceError(f"Polygon API error for {symbol}: {data.get('error', 'unknown')}")
        return []

    bars = []
    for r in results:
        ts_ms = r["t"]
        ts = date.fromtimestamp(ts_ms / 1000).isoformat()
        bars.append({
            "instrument_id": symbol.upper(),
            "timestamp": ts,
            "open": float(r["o"]),
            "high": float(r["h"]),
            "low": float(r["l"]),
            "close": float(r["c"]),
            "volume": int(r.get("v", 0)),
        })
    return bars


def fetch_batch(symbols: list[str], days: int = 500) -> dict[str, list[dict]]:
    """Fetch daily bars for multiple symbols.

    Returns dict mapping symbol -> list of bar dicts.
    """
    result = {}
    for sym in symbols:
        result[sym.upper()] = fetch_daily_bars(sym, days=days)
    return result
