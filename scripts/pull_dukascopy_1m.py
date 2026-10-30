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

from dukascopy_bi5 import (  # noqa: E402,I001
    aggregate_1m, candle_day_path, day_paths, load_candles, load_ticks,
    merge_candle_sides,
)

SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# Measured 2026-10-27: TTFB is 16-31s while the feed is cold and ~1.2s once warm,
# so the old 10s ceiling killed every successful fetch and marked whole days
# UNREACHABLE. That is why research/dukascopy_1m_ba_prior/ stayed empty.
MAX_TIME_S = 45
# The feed sheds load with HTTP 503 (107-byte body, sub-second) in bursts that
# clear on their own, so a 503 means "retry later", never "no data".
RETRY_BACKOFF_S = (2, 5, 12, 30)
HOURS_PER_DAY = 24
CONN_BUDGET = 8  # >=1/3 dead hours => treat day as unreachable (feed down), not closed

# WINDOWS: when this script is spawned detached (no console), every console
# child (curl.exe) would otherwise pop a NEW visible console window per call.
# CREATE_NO_WINDOW suppresses that; harmless no-op elsewhere.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _curl(url: str, tmp_path: str) -> tuple[int | None, int]:
    """Return (http_status, bytes_written); status None means no HTTP reply."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", tmp_path, "-w", "%{http_code}",
             "--max-time", str(MAX_TIME_S), "-A", UA, url],
            capture_output=True, text=True, timeout=MAX_TIME_S + 10,
            creationflags=NO_WINDOW,
        )
        if r.returncode != 0:
            return None, 0
        status = int((r.stdout or "").strip() or 0)
        size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        return status, size
    except Exception:
        return None, 0


def fetch_hour(url: str, tmp_path: str):
    """Return ('ok', ticks) | ('closed', []) | ('conn', None).

    'closed' requires HTTP 200 with a short body — an empty weekend/illiquid
    hour. Error bodies are never treated as closed, however small: curl writes
    them to the same file, so classifying on size alone would record missing
    data as a legitimately quiet market.
    """
    for delay in RETRY_BACKOFF_S + (None,):
        status, size = _curl(url, tmp_path)
        if status == 200:
            if size < 40:
                return ("closed", [])
            try:
                return ("ok", load_ticks(tmp_path))
            except Exception:
                return ("conn", None)  # 200 but undecodable => treat as failure
        if delay is None:
            return ("conn", None)
        time.sleep(delay)
    return ("conn", None)


def feed_healthy(probe_url: str) -> bool:
    """True if the datafeed answers a mid-session hour with real bytes."""
    status, size = _curl(probe_url, str(Path(os.environ.get("TEMP", "."))
                                        / f"dk_probe_{os.getpid()}.bi5"))
    return status == 200 and size > 40



def pull_candle_day(symbol: str, day: date, tmp_dir: Path) -> tuple[list[dict], bool]:
    """One UTC day of 1m bid/ask bars from vendor candles. Returns (bars, ok).

    Two requests per day instead of 24 hourly tick files. ok=False means the
    feed failed; an empty list with ok=True is a genuinely closed day.
    """
    sides: dict[str, dict[int, dict]] = {}
    for side in ("BID", "ASK"):
        tmp = tmp_dir / f"{day.isoformat()}_{side}.bi5"
        for delay in RETRY_BACKOFF_S + (None,):
            status, size = _curl(candle_day_path(symbol, day, side), str(tmp))
            if status == 200 and size < 40:
                return [], True  # closed day (weekend / holiday)
            if status == 200:
                try:
                    sides[side] = load_candles(str(tmp))
                    break
                except Exception:
                    pass
            if delay is None:
                return [], False
            time.sleep(delay)
    bars = []
    for bar in merge_candle_sides(sides["BID"], sides["ASK"]):
        m = bar.pop("minute")
        bars.append({"timestamp": f"{day.isoformat()}T{m // 60:02d}:{m % 60:02d}:00Z",
                     **bar})
    return bars, True


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
                for bar in aggregate_1m_ticks(ticks):
                    ts = f"{day.isoformat()}T{h:02d}:{bar['minute']:02d}:00Z"
                    day_bars.append({"timestamp": ts, **bar})
    return day_bars, conn_fail


def download_symbol_missing(symbol: str, start: date, days: int,
                            parallel_days: int = 2,
                            only_days: set | None = None,
                            checkpoint=None,
                            use_candles: bool = False) -> tuple[list[dict], list[str]]:
    """Pull `days` days from `start`; returns (bars, unreachable_iso_dates).

    parallel_days > 1 pulls multiple days concurrently (each day still uses
    its own 4-worker hour pool) — overlaps dead-day timeouts across days.

    only_days: optional set of ISO dates ('YYYY-MM-DD') to restrict the fetch
    to. When given, days not in the set are skipped entirely (used by the
    prior-window launcher so already-fetched days are never re-pulled).

    use_candles: fetch vendor-aggregated 1m candles (2 requests/day) instead of
    24 hourly tick files. Same output schema; `n` becomes bid volume.
    """
    bars_all: list[dict] = []
    unreachable: list[str] = []
    tmp_dir = Path(os.environ.get("TEMP", ".")) / f"dk_{os.getpid()}_{symbol}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    days_list = [start + timedelta(days=i) for i in range(days)]
    if only_days is not None:
        days_list = [d for d in days_list if d.isoformat() in only_days]

    def one(day):
        if use_candles:
            bars, ok = pull_candle_day(symbol, day, tmp_dir)
            if not ok:
                print(f"  {symbol} {day}: UNREACHABLE (candle feed down) - "
                      f"skipped, will retry", flush=True)
                return day.isoformat(), [], True
            print(f"  {symbol} {day}: {len(bars)} 1m bars"
                  if bars else f"  {symbol} {day}: closed/no ticks", flush=True)
            return day.isoformat(), bars, False
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