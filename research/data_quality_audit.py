"""Standalone data-quality audit for TITAN's research price data.

Checks any Dukascopy 1m bid/ask JSON (o_ask/h_ask/l_ask/c_ask, o_bid/h_bid/
l_bid/c_bid, n) or TWS-style OHLCV JSON (open/high/low/close/volume) for the
issues that would silently bias a backtest: duplicate timestamps, crossed
markets, zero-tick/stale bars, weekend leakage, and gaps that don't match the
expected FX weekly closure (~48h Fri close -> Sun reopen).

Usage:
    python research/data_quality_audit.py research/dukascopy_1m_ba/EURUSD.json
    python research/data_quality_audit.py research/tws_history/EURUSD.json
    python research/data_quality_audit.py research/dukascopy_1m_ba/*.json   (any shell that globs)

No third-party dependencies — stdlib only, safe to run against multi-hundred-MB files.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def audit_file(path: Path) -> None:
    print(f"\n{'='*70}\n{path}\n{'='*70}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  FAILED TO PARSE: {e}")
        return

    if not isinstance(data, list) or not data:
        print(f"  EMPTY OR NOT A LIST ({len(data) if isinstance(data, list) else type(data)}) "
              f"-- flag this file as unusable if any experiment references it.")
        return

    is_dukascopy = "c_bid" in data[0] and "c_ask" in data[0]
    is_ohlcv = "close" in data[0]

    n_total = len(data)
    seen = set()
    dupes = 0
    sat_bars = 0
    zero_tick = 0
    crossed = 0
    spreads = []
    prev_ts = None
    max_gap_min = 0.0
    gap_examples = []
    non_weekly_gaps = []  # gaps that aren't ~1 unit or the weekly ~48h closure
    vol_placeholder_count = 0

    for r in data:
        ts = _parse_ts(r["timestamp"])
        key = r["timestamp"]
        if key in seen:
            dupes += 1
        seen.add(key)

        if ts.weekday() == 5:  # Saturday should never appear for FX
            sat_bars += 1

        if is_dukascopy:
            if r.get("n") == 0:
                zero_tick += 1
            if r["c_ask"] < r["c_bid"]:
                crossed += 1
            spreads.append(r["c_ask"] - r["c_bid"])

        if is_ohlcv:
            if r.get("high", 0) < r.get("low", 0):
                crossed += 1
            if r.get("volume") in (-1, -1.0):
                vol_placeholder_count += 1

        if prev_ts is not None:
            gap = (ts - prev_ts).total_seconds() / 60
            if gap > max_gap_min:
                max_gap_min = gap
                gap_examples = [(prev_ts.isoformat(), ts.isoformat())]
            elif gap == max_gap_min:
                gap_examples.append((prev_ts.isoformat(), ts.isoformat()))
            # flag any gap that's neither ~1 bar nor a plausible weekly closure (40-52h)
            if gap > 5 and not (2400 <= gap <= 3120):
                non_weekly_gaps.append((prev_ts.isoformat(), ts.isoformat(), round(gap, 1)))
        prev_ts = ts

    print(f"  records:          {n_total}")
    print(f"  date range:       {data[0]['timestamp']}  ->  {data[-1]['timestamp']}")
    print(f"  duplicate ts:     {dupes}")
    print(f"  Saturday bars:    {sat_bars}  (should be 0)")
    print(f"  crossed market:   {crossed}  (should be 0)")
    print(f"  max gap (min):    {max_gap_min:.0f}  e.g. {gap_examples[:2]}")
    print(f"  unexplained gaps (not ~1 bar, not weekly closure): {len(non_weekly_gaps)}")
    for g in non_weekly_gaps[:10]:
        print(f"    - {g}")

    if is_dukascopy:
        print(f"  zero-tick bars:   {zero_tick} ({100*zero_tick/n_total:.3f}%)")
        spreads.sort()
        m = len(spreads)
        print(f"  spread (pips): min={spreads[0]*1e4:.2f} median={spreads[m//2]*1e4:.2f} "
              f"mean={statistics.fmean(spreads)*1e4:.2f} p95={spreads[int(m*0.95)]*1e4:.2f} "
              f"max={spreads[-1]*1e4:.2f}")
        print(f"  non-positive spread bars: {sum(1 for s in spreads if s <= 0)}")

    if is_ohlcv:
        print(f"  volume==-1 (placeholder) bars: {vol_placeholder_count} / {n_total}"
              f"  -- if <100%, some bars have real volume and some don't; check why")

    verdict_bad = dupes or sat_bars or crossed or (is_dukascopy and zero_tick) or non_weekly_gaps
    print(f"\n  VERDICT: {'ISSUES FOUND -- see above' if verdict_bad else 'clean'}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for arg in sys.argv[1:]:
        audit_file(Path(arg))


if __name__ == "__main__":
    main()
