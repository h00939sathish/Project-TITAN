"""Acquire short-horizon intraday research data and run non-routing backtests.

This script never instantiates a TITAN execution engine or connects to TWS.
SPY data comes from Alpaca's IEX historical-data API; EUR/USD uses yfinance
and is labelled unapproved research data in the generated manifest.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from dotenv import load_dotenv

from backtest_strategies import DEFAULT_PARAMS, STRATEGIES, run_strategy


OUTPUT_DIR = Path("research/intraday_backtests/2026-07-29")
TIMEFRAMES = {"5m": None, "15m": "15min", "1h": "1h"}
MAX_SOURCE_BARS = 3_000


def _to_frame(rows: list[dict], symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    if frame.empty or not frame.index.is_monotonic_increasing:
        raise ValueError(f"{symbol}: empty or non-monotonic source bars")
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def fetch_spy() -> pd.DataFrame:
    load_dotenv()
    client = StockHistoricalDataClient(
        os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"],
    )
    end = datetime.now(timezone.utc)
    request = StockBarsRequest(
        symbol_or_symbols="SPY",
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=end - timedelta(days=60),
        end=end,
        feed="iex",
    )
    bars = client.get_stock_bars(request).data.get("SPY", [])
    return _to_frame(
        [{
            "timestamp": bar.timestamp, "open": bar.open, "high": bar.high,
            "low": bar.low, "close": bar.close, "volume": bar.volume,
        } for bar in bars],
        "SPY",
    ).tail(MAX_SOURCE_BARS)


def fetch_eurusd() -> pd.DataFrame:
    raw = yf.download("EURUSD=X", period="60d", interval="5m", auto_adjust=False, progress=False)
    if raw.empty:
        raise ValueError("EURUSD: yfinance returned no 5-minute bars")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    rows = [{
        "timestamp": index, "open": row["Open"], "high": row["High"],
        "low": row["Low"], "close": row["Close"], "volume": row.get("Volume", 0),
    } for index, row in raw.iterrows()]
    return _to_frame(rows, "EURUSD").tail(MAX_SOURCE_BARS)


def aggregate(frame: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    if rule is None:
        return frame.copy()
    result = frame.resample(rule, label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()
    return result


def write_dataset(symbol: str, timeframe: str, frame: pd.DataFrame) -> tuple[Path, str]:
    output = OUTPUT_DIR / f"{symbol.lower()}_{timeframe}.csv"
    data = frame.reset_index()
    data.insert(1, "symbol", symbol)
    data.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return output, digest


def backtest(frame: pd.DataFrame) -> dict:
    bars = [
        {"timestamp": index.isoformat(), "open": row.open, "high": row.high,
         "low": row.low, "close": row.close, "volume": int(row.volume)}
        for index, row in frame.iterrows()
    ]
    return {
        strategy_id: run_strategy(bars, factory, DEFAULT_PARAMS[strategy_id], capital_pct=10.0)
        for strategy_id, factory in STRATEGIES.items()
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets = {
        "SPY": (fetch_spy(), "Alpaca IEX historical bars"),
        "EURUSD": (fetch_eurusd(), "Yahoo Finance via yfinance — unapproved research source"),
    }
    manifest: dict[str, object] = {"generated_at": datetime.now(timezone.utc).isoformat(), "assets": {}}
    results: dict[str, object] = {}
    for symbol, (source_frame, source) in assets.items():
        manifest["assets"][symbol] = {"source": source, "timeframes": {}}
        results[symbol] = {}
        for name, rule in TIMEFRAMES.items():
            frame = aggregate(source_frame, rule)
            output, digest = write_dataset(symbol, name, frame)
            coverage = {"rows": len(frame), "from": frame.index[0].isoformat(), "to": frame.index[-1].isoformat()}
            manifest["assets"][symbol]["timeframes"][name] = {**coverage, "path": str(output), "sha256": digest}
            results[symbol][name] = {**coverage, "strategies": backtest(frame)}
            print(f"{symbol} {name}: {coverage['rows']} bars ({coverage['from']} to {coverage['to']})")
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
