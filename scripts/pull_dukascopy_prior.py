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
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import pull_dukascopy_1m as dk  # reuse resilient hour/aggregate/merge logic


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--symbol", action="append", default=[])
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

        # pull the missing days one contiguous block (start..end); the resilient
        # downloader skips 'closed' days and retlog unreachable ones.
        bars, unreachable = dk.download_symbol_missing(sym, args.start, days)
        merged = existing + bars
        merged.sort(key=lambda b: b["timestamp"])
        out.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        n = len(merged)
        span = (merged[0]["timestamp"][:10] + " -> " + merged[-1]["timestamp"][:10]) if n else "EMPTY"
        print(f"  {sym}: {n} bars ({span}) -> {out}", flush=True)
        if unreachable:
            print(f"  {sym}: {len(unreachable)} UNREACHABLE days: "
                  f"{unreachable[0]}..{unreachable[-1]} — re-run to retry", flush=True)


if __name__ == "__main__":
    main()