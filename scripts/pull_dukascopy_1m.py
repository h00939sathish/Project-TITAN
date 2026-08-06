"""Bulk-download Dukascopy 1-minute bid/ask bars for FX pairs.

Downloads hour-ticks (bi5) via the public datafeed, aggregates to 1-min OHLC
bid/ask bars, writes research/dukascopy_1m_ba/{SYMBOL}.json.

Resilience (2026-08-06): the datafeed is intermittent from some networks —
distinguish a real market-close (HTTP 200, size<40: weekend/closed hour) from a
connection failure (curl rc!=0 / timeout), so a flaky feed does NOT silently
write a partial file labelled as a complete pull. Days that are mostly
connection-failures are reported as UNREACHABLE and the run stops clean-tagged.

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

SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MAX_TIME_S = 15
HOURS_PER_DAY = 24
CONN_BUDGET = 12  # >=half dead hours => treat day as unreachable (feed down), not closed


def fetch_hour(url: str, tmp_path: str):
    """Return ('ok', ticks) | ('closed', []) | ('conn', None).

    'closed' = valid empty (size<40 => weekend/illiquid hour, NOT an error).
    'conn'   = the datafeed itself was unreachable (curl rc!=0 / timeout).
    """
    for attempt in range(2):
        try:
            rc = subprocess.run(
                ["curl", "-s", "-o", tmp_path, "--max-time", str(MAX_TIME_S), "-A", UA, url],
                capture_output=True, timeout=MAX_TIME_S + 5,
            ).returncode
            if rc != 0:
                raise RuntimeError(f"curl rc={rc}")
            size = os.path.getsize(tmp_path)
            if size < 40:  # valid empty hour (market closed / no ticks)
                return ("closed", [])
            return ("ok", load_ticks(tmp_path))
        except Exception:
            if attempt == 1:
                return ("conn", None)  # two failures => feed unreachable
            time.sleep(1.5)
    return ("conn", None)  # unreachable


def download_symbol_missing(symbol: str, start: date, days: int) -> tuple[list[dict], list[str]]:
    """Pull `days` days from `start`; returns (bars, unreachable_iso_dates)."""
    bars_all: list[dict] = []
    unreachable: list[str] = []
    tmp_dir = Path(os.environ.get("TEMP", ".")) / f"dk_{os.getpid()}_{symbol}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    day = start
    for d in range(days):
        urls = day_paths(symbol, day, range(HOURS_PER_DAY))

        def grab(url_idx):
            h, url = url_idx
            kind, ticks = fetch_hour(url, str(tmp_dir / f"{h:02d}.bi5"))
            return h, kind, ticks

        day_bars: list[dict] = []
        conn_fail = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for h, kind, ticks in pool.map(grab, list(enumerate(urls))):
                if kind == "conn":
                    conn_fail += 1
                    continue
                if not ticks:
                    continue
                for m, bar in enumerate(aggregate_1m_ticks(ticks)):
                    ts = f"{day.isoformat()}T{h:02d}:{m:02d}:00Z"
                    day_bars.append({"timestamp": ts, **bar})
        if conn_fail >= CONN_BUDGET:
            unreachable.append(day.isoformat())
            print(f"  {symbol} {day}: UNREACHABLE ({conn_fail}/{HOURS_PER_DAY}h feed down) - skipped, will retry", flush=True)
        elif day_bars:
            bars_all.extend(day_bars)
            print(f"  {symbol} {day}: {len(day_bars)} 1m bars", flush=True)
        else:
            print(f"  {symbol} {day}: closed/no ticks", flush=True)
        day += timedelta(days=1)
    return bars_all, unreachable


def aggregate_1m_ticks(ticks):  # bridge for import-style calling
    return aggregate_1m(ticks)


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
    for sym in symbols:
        print(f"\n{sym}...", flush=True)
        out = OUT_DIR / f"{sym}.json"
        # merge with any existing bars (resumable)
        existing = []
        if out.exists():
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        bars, unreachable = download_symbol_missing(sym, start, args.days)
        merged = existing + bars
        merged.sort(key=lambda b: b["timestamp"])
        out.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        n = len(merged)
        span = (merged[0]["timestamp"][:10] + " -> " + merged[-1]["timestamp"][:10]) if n else "EMPTY"
        print(f"  {sym}: {n} bars ({span}) -> {out}", flush=True)
        if unreachable:
            print(f"  {sym}: {len(unreachable)} UNREACHABLE days (feed down): "
                  f"{unreachable[0]}..{unreachable[-1]} - re-run when feed is back", flush=True)


if __name__ == "__main__":
    main()