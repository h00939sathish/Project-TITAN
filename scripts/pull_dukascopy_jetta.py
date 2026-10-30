"""Pull Dukascopy 1m bid/ask bars from the widget candle API.

The bi5 datafeed (datafeed.dukascopy.com) costs ~22 s per request and pads
every closed minute with a flat zero-volume bar. The endpoint behind the public
"Historical data export" widget (jetta.dukascopy.com) serves the same candles
as JSON in ~0.5 s, and returns only minutes that actually traded -- a Saturday
comes back with an empty array instead of 1440 fake bars.

Verified 2026-10-27 against three independent sources: the widget's CSV export
for 2022-01-04, the decoded bi5 candle file for 2022-11-03, and this API.
1435 bars each, zero OHLC differences, identical minute sets.

Payload is columnar and delta-encoded:
  times        deltas in units of `shift` ms, seeded by `timestamp`
  o/h/l/c      integer deltas in units of `multiplier`, seeded by the scalar
               open/high/low/close
  volumes      absolute floats
A day with no trading has `open: null` and empty arrays, which is valid.

Two headers are mandatory: without Origin/Referer the CDN answers 403 HTML.

Run: python scripts/pull_dukascopy_jetta.py --start 2022-08-01 --end 2025-07-31
"""
import argparse
import itertools
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "research" / "dukascopy_1m_ba_prior"
SYMBOLS = {"EURUSD": "EUR-USD", "GBPUSD": "GBP-USD",
           "AUDUSD": "AUD-USD", "NZDUSD": "NZD-USD"}
BASE = "https://jetta.dukascopy.com/v1/candles/minute/{code}/{side}/{y}/{m}/{d}"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://widgets.dukascopy.com",
    "Referer": "https://widgets.dukascopy.com/en/historical-data-export",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"),
}
RETRY_DELAYS = (1, 3, 8, 20)
CHECKPOINT_DAYS = 25


def fetch_day(code: str, side: str, day: date) -> dict:
    url = BASE.format(code=code, side=side, y=day.year, m=day.month, d=day.day)
    last = None
    for delay in RETRY_DELAYS + (None,):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
                if r.status != 200:
                    raise RuntimeError(f"http {r.status}")
                return json.loads(r.read())
        except Exception as exc:  # noqa: BLE001 - any failure is retryable
            last = exc
            if delay is None:
                break
            time.sleep(delay)
    raise RuntimeError(f"{url}: {last}")


def decode_day(payload: dict) -> dict[int, tuple]:
    """-> {epoch_second: (o, h, l, c, volume)} for the minutes that traded."""
    if not payload.get("times"):
        return {}
    mult = payload["multiplier"]
    shift = payload["shift"]
    base = payload["timestamp"]
    out = {}
    ticks = itertools.accumulate(payload["times"])
    for i, (tick, do, dh, dl, dc) in enumerate(zip(
            ticks, itertools.accumulate(payload["opens"]),
            itertools.accumulate(payload["highs"]), itertools.accumulate(payload["lows"]),
            itertools.accumulate(payload["closes"]))):
        secs = (base + tick * shift) // 1000
        out[secs] = (round(payload["open"] + do * mult, 5),
                     round(payload["high"] + dh * mult, 5),
                     round(payload["low"] + dl * mult, 5),
                     round(payload["close"] + dc * mult, 5),
                     round(payload["volumes"][i], 2))
    return out


def pull_day(code: str, day: date) -> list[dict]:
    """Both sides for one UTC day, joined on minute. Empty list = no trading."""
    bid = decode_day(fetch_day(code, "BID", day))
    if not bid:
        return []
    ask = decode_day(fetch_day(code, "ASK", day))
    bars = []
    for secs in sorted(set(bid) & set(ask)):
        b, a = bid[secs], ask[secs]
        if a[3] < b[3]:
            continue  # crossed book - drop rather than publish a bad spread
        ts = datetime.fromtimestamp(secs, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        bars.append({"timestamp": ts,
                     "o_ask": a[0], "h_ask": a[1], "l_ask": a[2], "c_ask": a[3],
                     "o_bid": b[0], "h_bid": b[1], "l_bid": b[2], "c_bid": b[3],
                     "n": b[4]})
    return bars


def write_merged(path: Path, existing: list[dict], new: list[dict]) -> list[dict]:
    merged = existing + new
    merged.sort(key=lambda b: b["timestamp"])
    deduped = []
    last = None
    for bar in merged:
        if bar["timestamp"] != last:
            deduped.append(bar)
            last = bar["timestamp"]
    atomic_write(path, lambda: _json_array(deduped))
    return deduped


def _json_array(bars: list[dict]) -> Iterator[str]:
    """Yield the array in batches so no single multi-hundred-MB string is built.

    json.dumps over the whole 1.1M-bar list with indent=1 raised MemoryError:
    indent forces the pure-Python encoder, which accumulates a piece per token
    and then joins them -- on top of a ~1 GB dict graph.
    """
    encode = json.JSONEncoder(separators=(",", ":")).encode
    yield "["
    first = True
    batch: list[str] = []
    for bar in bars:
        batch.append(encode(bar))
        if len(batch) == 2000:
            yield ("" if first else ",") + ",".join(batch)
            first = False
            batch = []
    if batch:
        yield ("" if first else ",") + ",".join(batch)
    yield "]"


def atomic_write(path: Path, chunks: Callable[[], Iterator[str]]) -> None:
    """Write via a sibling temp file + os.replace.

    Two hazards this survives. A direct write_text leaves a truncated JSON if
    the process dies mid-write. And on this machine the checkpoint fails once
    the file passes ~140 MB: os.replace returns WinError 5 because a real-time
    scanner is holding the freshly written file, then the next open of the .tmp
    returns errno 22 off the same lock. Both clear on their own within seconds,
    so retry patiently -- a 4 s budget was not enough.

    `chunks` is a factory rather than an iterator so a retry can regenerate
    the body.
    """
    tmp = path.with_name(path.name + ".tmp")
    last_exc: OSError | None = None
    delays = (0, 2, 5, 10, 20, 30, 30, 30)
    for attempt, delay in enumerate(delays, start=1):
        time.sleep(delay)
        try:
            with tmp.open("w", encoding="utf-8") as f:
                for chunk in chunks():
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            if attempt > 1:
                print(f"  [write] {path.name}: recovered on attempt {attempt}",
                      flush=True)
            return
        except OSError as exc:  # noqa: PERF203
            last_exc = exc
            print(f"  [write] {path.name}: attempt {attempt}/{len(delays)} failed: {exc}",
                  flush=True)
    raise last_exc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--symbol", action="append", default=[])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    days = (args.end - args.start).days + 1
    if days <= 0:
        raise SystemExit("start must be <= end")
    calendar = [args.start + timedelta(days=i) for i in range(days)]
    # Saturdays never trade; the API returns an empty day for them, so requiring
    # them would make every resume re-fetch ~157 dead days per symbol.
    required = [d for d in calendar if d.weekday() != 5]
    wanted = args.symbol or list(SYMBOLS)
    print(f"{args.start}..{args.end}: {len(required)} required days "
          f"({len(calendar) - len(required)} Saturdays skipped) -> {out_dir}")

    for sym in wanted:
        code = SYMBOLS[sym]
        path = out_dir / f"{sym}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        have = {b["timestamp"][:10] for b in existing}
        missing = [d for d in required if d.isoformat() not in have]
        print(f"\n{sym}: {len(existing)} bars on disk, {len(missing)} days to fetch",
              flush=True)
        if not missing:
            continue

        started = time.time()
        done = 0
        failures = []
        new_bars: list[dict] = []

        def one(day: date):
            try:
                return day, pull_day(code, day), None
            except Exception as exc:  # noqa: BLE001
                return day, [], str(exc)

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for day, bars, err in pool.map(one, missing):
                done += 1
                if err:
                    failures.append(day)
                    print(f"  {sym} {day}: FAILED {err}", flush=True)
                else:
                    new_bars.extend(bars)
                if done % CHECKPOINT_DAYS == 0:
                    existing = write_merged(path, existing, new_bars)
                    new_bars = []
                    rate = (time.time() - started) / done
                    left = len(missing) - done
                    print(f"  [ckpt {sym}] {done}/{len(missing)} days, "
                          f"{len(existing)} bars, {rate*1000:.0f} ms/day, "
                          f"eta {left*rate/60:.0f} min", flush=True)

        existing = write_merged(path, existing, new_bars)
        n = len(existing)
        span = (f"{existing[0]['timestamp'][:10]} -> {existing[-1]['timestamp'][:10]}"
                if n else "EMPTY")
        print(f"{sym}: {n} bars ({span}) in {(time.time()-started)/60:.1f} min", flush=True)
        if failures:
            print(f"{sym}: {len(failures)} days failed: "
                  f"{[d.isoformat() for d in failures[:5]]}{'...' if len(failures) > 5 else ''}",
                  flush=True)


if __name__ == "__main__":
    main()
