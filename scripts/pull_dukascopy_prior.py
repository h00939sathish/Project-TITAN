"""Pull a PRIOR, non-overlapping Dukascopy 1m window (OOS inventory).

Distinct from pull_dukascopy_1m.py (which writes the live/in-sample window and
hardcodes end=2026-07-31). This launcher imports the same resilient bi5
downloader but writes to a SEPARATE dir and targets an explicit date range, so
the in-sample set (research/dukascopy_1m_ba) is never contaminated.

Supports the debated WF-v2 Step 5 (primary: prior multi-year window). Writes to
research/dukascopy_1m_ba_prior/{SYMBOL}.json, resumable per symbol.

Run: python scripts/pull_dukascopy_prior.py --start 2022-08-01 --end 2025-07-31 \
       --symbol EURUSD [--symbol GBPUSD]
"""
import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import pull_dukascopy_1m as dk  # reuse resilient hour/aggregate/merge logic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--symbol", action="append", default=[])
    ap.add_argument("--parallel", type=int, default=1,
                    help="concurrent days to pull (default 1 = sequential); "
                         "NOTE: >1 measured SLOWER on this feed (server throttle), "
                         "kept as opt-in only")
    args = ap.parse_args()
    symbols = args.symbol or dk.SYMBOLS
    if not args.symbol:
        print("WARNING: no --symbol given, pulling all SYMBOLS")
    days = (args.end - args.start).days + 1
    if days <= 0:
        print("ERROR: start must be <= end")
        sys.exit(2)

    pri = Path(__file__).resolve().parents[1] / "research" / "dukascopy_1m_ba_prior"
    pri.mkdir(parents=True, exist_ok=True)
    print(f"PRIOR window {args.start}..{args.end} ({days}d) -> {pri}")

    for sym in symbols:
        out = pri / f"{sym}.json"
        existing = []
        if out.exists():
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        # skip if we already span most of the requested range (resume-friendly)
        req = {(args.start + timedelta(days=step)).isoformat() for step in range(days)}
        have = {b["timestamp"][:10] for b in existing}
        missing = req - have
        print(f"\n{sym}: existing {len(existing)} bars, {len(missing)} prior-days missing", flush=True)
        if not missing:
            print(f"  {sym}: already complete, skip", flush=True)
            continue

        # pull ONLY the missing days (already-fetched days are never re-pulled;
        # the resilient downloader skips 'closed' days and retlogs unreachable).
        # checkpoint() persists merged+deduped progress every 10 processed days,
        # so a session death no longer discards in-memory bars.
        def checkpoint(new_bars):
            merged = existing + new_bars
            merged.sort(key=lambda b: b["timestamp"])
            deduped = []
            last = None
            for b in merged:
                if b["timestamp"] != last:
                    deduped.append(b)
                    last = b["timestamp"]
            out.write_text(json.dumps(deduped, indent=1), encoding="utf-8")
            print(f"  [ckpt {sym}] {len(new_bars)} new bars -> "
                  f"{len(deduped)} total on disk", flush=True)

        probe_url = (f"https://datafeed.dukascopy.com/datafeed/{sym}/"
                     f"2025/06/15/12h_ticks.bi5")
        for attempt in range(10):
            if dk.feed_healthy(probe_url):
                print(f"  {sym}: feed reachable (probe OK)", flush=True)
                break
            print(f"  {sym}: feed down (probe {attempt + 1}/10), waiting 10s...",
                  flush=True)
            time.sleep(10)
        else:
            print(f"  {sym}: WARNING feed unreachable after ~2min - launching "
                  f"anyway (dead days skip as UNREACHABLE, retried in-run)",
                  flush=True)

        bars, unreachable = dk.download_symbol_missing(sym, args.start, days,
                                              parallel_days=args.parallel,
                                              only_days=missing,
                                              checkpoint=checkpoint)
        # in-run retry: feed flaps recover in minutes, so re-pull the days that
        # failed before giving up (up to 3 passes). Drop partial pass-1 bars for
        # retried days so the fuller pass-2 bars win (dedup keeps first occurrence).
        for retry in range(3):
            if not unreachable:
                break
            bad_days = set(unreachable)
            bars = [b for b in bars if b["timestamp"][:10] not in bad_days]
            print(f"  {sym}: retry pass {retry + 1}/3 for "
                  f"{len(bad_days)} unreachable days", flush=True)
            bars2, unreachable = dk.download_symbol_missing(
                sym, args.start, days,
                parallel_days=args.parallel,
                only_days=bad_days)
            bars = bars + bars2
        merged = existing + bars
        # idempotent merge: sort by timestamp, then drop exact-duplicate
        # timestamps (missing-day detection is per-day, but the downloader
        # re-fetches the whole window, so overlap re-pulls would otherwise
        # duplicate bars). Keeps the first occurrence of each timestamp.
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
            print(f"  {sym}: {len(unreachable)} UNREACHABLE days: "
                  f"{unreachable[0]}..{unreachable[-1]} — re-run to retry", flush=True)


if __name__ == "__main__":
    main()