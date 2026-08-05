#!/usr/bin/env python3
"""Fetch real SPY/QQQ/TLT daily OHLCV from yfinance (2020-01-01 to 2024-12-31).

Usage:
    python scripts/fetch_real_data.py          # idempotent (skips if exists)
    python scripts/fetch_real_data.py --force  # re-download regardless
"""

import argparse
import csv
import hashlib
from pathlib import Path

FIXTURES_DIR = Path("tests/fixtures/market")
SYMBOLS = ["SPY", "QQQ", "TLT"]
START = "2020-01-01"
END = "2024-12-31"
OUTPUTS = {
    "SPY": FIXTURES_DIR / "real_spy_2020_2024.csv",
    "QQQ": FIXTURES_DIR / "real_qqq_2020_2024.csv",
    "TLT": FIXTURES_DIR / "real_tlt_2020_2024.csv",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def fetch_symbol(symbol: str) -> list[dict]:
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=START, end=END, auto_adjust=False)
    bars = []
    for date, row in df.iterrows():
        bars.append({
            "symbol": symbol,
            "date": date.strftime("%Y-%m-%d"),
            "open": f"{row['Open']:.2f}",
            "high": f"{row['High']:.2f}",
            "low": f"{row['Low']:.2f}",
            "close": f"{row['Close']:.2f}",
            "volume": str(int(row['Volume'])),
        })
    return bars


def write_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(bars)
    print(f"Wrote {len(bars)} bars to {path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch real SPY/QQQ/TLT daily data from yfinance")
    parser.add_argument("--force", action="store_true", help="Re-download even if files exist")
    args = parser.parse_args()

    for symbol in SYMBOLS:
        outpath = OUTPUTS[symbol]
        if outpath.exists() and not args.force:
            digest = sha256_file(outpath)
            print(f"SKIP {symbol}: {outpath.name} exists (SHA-256: {digest})")
            continue

        print(f"Downloading {symbol} from {START} to {END}...")
        bars = fetch_symbol(symbol)
        write_csv(bars, outpath)
        digest = sha256_file(outpath)
        print(f"SHA-256: {digest}")
        print()

    print("=== Final Checksums ===")
    for symbol in SYMBOLS:
        outpath = OUTPUTS[symbol]
        if outpath.exists():
            digest = sha256_file(outpath)
            print(f"  {outpath.name}: {digest}")
        else:
            print(f"  {outpath.name}: MISSING")


if __name__ == "__main__":
    main()
