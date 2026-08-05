"""Bulk-download Dukascopy 1-minute bid/ask bars for FX pairs.

Downloads hour-ticks (bi5) via the public datafeed, aggregates to 1-min OHLC
bid/ask bars, writes research/dukascopy_1m_ba/{SYMBOL}.json.

Run:  python scripts/pull_dukascopy_1m.py [--days 61] [--symbol EURUSD]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from dukascopy_bi5 import aggregate_1m, day_paths, load_ticks  # noqa: E402

SYMBOLS = ["EURUSD", "GBPUSD"]
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch_hour(url: str, tmp_path: str) -> list[tuple[int, float, float]]:
    for attempt in range(3):
        try:
            rc = subprocess.run(
                ["curl", "-s", "-o", tmp_path, "--max-time", "25", "-A", UA, url],
                capture_output=True, timeout=30,
            ).returncode
            if rc != 0:
                raise RuntimeError(f"curl rc={rc}")
            size = os.path.getsize(tmp_path)
            if size < 40:  # empty/404 (weekend hours, closed market)
                return []
            return load_ticks(tmp_path)
        except Exception:
            if attempt == 2:
                return []  # treat as missing hour (weekend / gap)
            time.sleep(1.5 * (attempt + 1))
    return []


def download_symbol(symbol: str, start: date, days: int) -> list[dict]:
    bars_all: list[dict] = []
    tmp_dir = Path(os.environ.get("TEMP", ".")) / f"dk_{os.getpid()}_{symbol}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    day = start
    for d in range(days):
        urls = day_paths(symbol, day, range(24))

        def grab(url_idx):
            h, url = url_idx
            return h, fetch_hour(url, str(tmp_dir / f"{h:02d}.bi5"))

        day_bars: list[dict] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for h, ticks in pool.map(grab, list(enumerate(urls))):
                if not ticks:
                    continue
                for m, bar in enumerate(aggregate_1m(ticks)):
                    ts = f"{day.isoformat()}T{h:02d}:{m:02d}:00Z"
                    day_bars.append({"timestamp": ts, **bar})
        if day_bars:
            bars_all.extend(day_bars)
            print(f"  {symbol} {day}: {len(day_bars)} 1m bars", flush=True)
        day += timedelta(days=1)
    return bars_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=61)
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()
    symbols = [args.symbol] if args.symbol else SYMBOLS

    end = date(2026, 7, 31)
    start = end - timedelta(days=args.days - 1)
    print(f"Pulling {symbols} from {start} to {end} ({(end - start).days + 1} days)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[dict]] = {}
    for sym in symbols:
        print(f"\n{sym}...", flush=True)
        results[sym] = download_symbol(sym, start, args.days)
        out = OUT_DIR / f"{sym}.json"
        out.write_text(json.dumps(results[sym], indent=1), encoding="utf-8")
        n = len(results[sym])
        span = (results[sym][0]["timestamp"][:10] + " -> " + results[sym][-1]["timestamp"][:10]) if n else "EMPTY"
        print(f"  {sym}: {n} bars ({span}) -> {out}", flush=True)


if __name__ == "__main__":
    main()
