"""Pull long daily OHLC history for FX pairs from Yahoo's chart API.

Writes research/tws_daily/{SYMBOL}.json (same shape as the TWS daily pull).
Pairs: EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, USDSEK, USDNOK, AUDUSD, NZDUSD.

Run:  python scripts/pull_yahoo_daily.py
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "tws_daily"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "USDSEK", "USDNOK", "AUDUSD", "NZDUSD"]


def fetch(symbol: str) -> list[dict]:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}=X"
           f"?range=8y&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    r = d["chart"]["result"][0]
    ts, q = r["timestamp"], r["indicators"]["quote"][0]
    rows = []
    for t, o, h, lo, c, v in zip(ts, q["open"], q["high"], q["low"], q["close"], q["volume"]):
        if t and c:
            rows.append({
                "instrument_id": symbol,
                "timestamp": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": o, "high": h, "low": lo, "close": c, "volume": v,
            })
    return rows


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sym in PAIRS:
        out = OUT_DIR / f"{sym}.json"
        if out.exists():
            print(f"{sym}: exists, skip")
            continue
        try:
            rows = fetch(sym)
            out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(f"{sym}: {len(rows)} bars ({rows[0]['timestamp'][:10]} -> {rows[-1]['timestamp'][:10]})")
        except Exception as e:
            print(f"{sym}: FAILED ({e})")
        time.sleep(0.7)


if __name__ == "__main__":
    main()
