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
MAX_TIME_S = 10
HOURS_PER_DAY = 24
CONN_BUDGET = 8  # >=1/3 dead hours => treat day as unreachable (feed down), not closed
# WINDOWS: when this script is spawned detached (no console), every console
# child (curl.exe) would otherwise pop a NEW visible console window per call.
# CREATE_NO_WINDOW suppresses that; harmless no-op elsewhere.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
                creationflags=NO_WINDOW,
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


def feed_healthy(probe_url: str) -> bool:
    """True if the datafeed answers a mid-session hour with real bytes."""
    tmp = Path(os.environ.get("TEMP", ".")) / f"dk_probe_{os.getpid()}.bi5"
    try:
        rc = subprocess.run(["curl", "-s", "-o", str(tmp), "--max-time", "12",
                             "-A", UA, probe_url],
                            capture_output=True, timeout=18,
                            creationflags=NO_WINDOW).returncode
        if rc != 0:
            return False
        return os.path.getsize(tmp) > 40
    except Exception:
        return False


def _pull_one_day(symbol: str, day: date, tmp_dir: Path):
    """Fetch one day's hours (early-bail once CONN_BUDGET dead hours hit).
    Returns (bars, conn_fail)."""
    urls = day_paths(symbol, day, range(HOURS_PER_DAY))

    day_bars: list[dict] = []
    conn_fail = 0
    pending = list(enumerate(urls))
    # per-day tmp subdir so parallel days never collide on the same .bi5 name
    day_tmp = tmp_dir / day.isoformat().replace("-", "")
    day_tmp.mkdir(parents=True, exist_ok=True)

    def grab(url_idx):
        h, url = url_idx
        kind, ticks = fetch_hour(url, str(day_tmp / f"{h:02d}.bi5"))
        return h, kind, ticks

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(grab, u) for u in pending]
        from concurrent.futures import as_completed
        for fut in as_completed(futs):
            if conn_fail >= CONN_BUDGET:
                # early bail: day is unreachable, cancel remaining hours
                for f in futs:
                    f.cancel()
                break
            h, kind, ticks = fut.result()
            if kind == "conn":
                conn_fail += 1
            elif ticks:
                for m, bar in enumerate(aggregate_1m_ticks(ticks)):
                    ts = f"{day.isoformat()}T{h:02d}:{m:02d}:00Z"
                    day_bars.append({"timestamp": ts, **bar})
    return day_bars, conn_fail


def download_symbol_missing(symbol: str, start: date, days: int,
                            parallel_days: int = 2,
                            only_days: set | None = None,
                            checkpoint=None) -> tuple[list[dict], list[str]]:
    """Pull `days` days from `start`; returns (bars, unreachable_iso_dates).

    parallel_days > 1 pulls multiple days concurrently (each day still uses
    its own 4-worker hour pool) — overlaps dead-day timeouts across days.

    only_days: optional set of ISO dates ('YYYY-MM-DD') to restrict the fetch
    to. When given, days not in the set are skipped entirely (used by the
    prior-window launcher so already-fetched days are never re-pulled).
    """
    bars_all: list[dict] = []
    unreachable: list[str] = []
    tmp_dir = Path(os.environ.get("TEMP", ".")) / f"dk_{os.getpid()}_{symbol}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    days_list = [start + timedelta(days=i) for i in range(days)]
    if only_days is not None:
        days_list = [d for d in days_list if d.isoformat() in only_days]

    def one(day):
        bars, conn_fail = _pull_one_day(symbol, day, tmp_dir)
        if conn_fail >= CONN_BUDGET:
            print(f"  {symbol} {day}: UNREACHABLE ({conn_fail}/{HOURS_PER_DAY}h feed down) - skipped, will retry", flush=True)
            return day.isoformat(), [], True
        if bars:
            print(f"  {symbol} {day}: {len(bars)} 1m bars", flush=True)
        else:
            print(f"  {symbol} {day}: closed/no ticks", flush=True)
        return day.isoformat(), bars, False

    if parallel_days > 1:
        with ThreadPoolExecutor(max_workers=parallel_days) as pool:
            for iso, bars, bad in pool.map(one, days_list):
                if bad:
                    unreachable.append(iso)
                else:
                    bars_all.extend(bars)
    else:
        days_done = 0
        for iso, bars, bad in map(one, days_list):
            days_done += 1
            if bad:
                unreachable.append(iso)
            else:
                bars_all.extend(bars)
            if checkpoint is not None and days_done % 10 == 0:
                checkpoint(bars_all)
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
        # idempotent merge: sort by timestamp, drop exact-duplicate timestamps
        merged.sort(key=lambda b: b["timestamp"])
        n0 = len(merged)
        deduped = []
        last = None
        for b in merged:
            if b["timestamp"] != last:
                deduped.append(b)
                last = b["timestamp"]
        merged = deduped
        if len(merged) != n0:
            print(f"  {sym}: dedup removed {n0 - len(merged)} duplicate bars", flush=True)
        out.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        n = len(merged)
        span = (merged[0]["timestamp"][:10] + " -> " + merged[-1]["timestamp"][:10]) if n else "EMPTY"
        print(f"  {sym}: {n} bars ({span}) -> {out}", flush=True)
        if unreachable:
            print(f"  {sym}: {len(unreachable)} UNREACHABLE days (feed down): "
                  f"{unreachable[0]}..{unreachable[-1]} - re-run when feed is back", flush=True)


if __name__ == "__main__":
    main()