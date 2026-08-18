#!/usr/bin/env python3
"""Step 0 audit for EXP-FX-002 (structural price-action ablation).

Determines, per pair, whether the Dukascopy 1m bid/ask archive satisfies the
pre-registered data contract:
  - window        : 2021-08-01T00:00Z .. 2025-07-31T23:59Z (prior archive) or
                    fallback window in the post-2025-08 archive
  - contiguous    : >= 24 contiguous months with data
  - missing ticks : < 5% (1 - unique_bars / (1440 * Mon-Fri days-in-window))
  - integrity     : no duplicate timestamps (concurrent-writer damage check)

Applies the R6 tiered verdict over the six-pair universe:
  <4 qualifying pairs  -> DATA-UNAVAILABLE (no promotion analysis)
  4-5 qualifying pairs -> EXPLORATORY only (no full-universe replication claim)
  6 qualifying pairs   -> full EXP-FX-002 analysis

Usage:
  python research/exp_fx_002/step0_audit.py [--pairs eurusd,gbpusd,...]

Output: JSON summary to stdout, full per-pair table to stdout, and a verdict line.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNIVERSE = ["eurusd", "gbpusd", "usdjpy", "usdchf", "usdcad", "audusd"]
PRIOR_DIR = REPO / "research" / "dukascopy_1m_ba_prior"
BA_DIR = REPO / "research" / "dukascopy_1m_ba"
WINDOW_START = datetime(2021, 8, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 7, 31, 23, 59, tzinfo=timezone.utc)
MIN_CONTIG_MONTHS = 24
MAX_MISSING_TICK_RATE = 0.05
MIN_QUALIFYING = 4
FULL_UNIVERSE = 6


def count_weekdays(start: datetime, end: datetime) -> int:
    """Number of Mon-Fri days in [start, end] inclusive."""
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def month_spans(timestamps: list[datetime]) -> tuple[int, int]:
    """Return (n_contiguous_months, max_gap_months) across the window."""
    months = sorted({(t.year, t.month) for t in timestamps})
    if not months:
        return 0, 0
    contig = best = 1
    for i in range(1, len(months)):
        y0, m0 = months[i - 1]
        y1, m1 = months[i]
        gap = (y1 * 12 + m1) - (y0 * 12 + m0)
        if gap == 1:
            contig += 1
            best = max(best, contig)
        else:
            contig = 1
    return best, len(months)


def audit_pair(name: str, path: Path) -> dict:
    """Audit a single pair file against the contract. Never raises on data
    problems — returns a status dict instead."""
    result = {
        "pair": name,
        "file": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "status": "MISSING",
        "details": {},
    }
    if not path.exists() or path.stat().st_size < 1000:
        return result

    try:
        with path.open(encoding="utf-8") as f:
            bars = json.load(f)
    except Exception as e:  # noqa: BLE001 - audit must never crash
        result["status"] = "CORRUPT"
        result["details"]["error"] = str(e)
        return result

    n_total = len(bars)
    ts_raw = [b.get("timestamp", "") for b in bars]
    n_unique = len(set(ts_raw))
    dups = n_total - n_unique
    result["details"]["total_bars"] = n_total
    result["details"]["unique_bars"] = n_unique
    result["details"]["duplicate_timestamps"] = dups

    if dups > 0:
        result["status"] = "DAMAGED_DUPES"
        result["details"]["note"] = (
            "concurrent-writer signature; run scripts/dedup_bars_json.py before any analysis"
        )
        return result

    try:
        t0 = datetime.fromisoformat(ts_raw[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(ts_raw[-1].replace("Z", "+00:00"))
    except Exception as e:  # noqa: BLE001
        result["status"] = "CORRUPT"
        result["details"]["error"] = f"timestamp parse: {e}"
        return result

    result["details"]["first_ts"] = t0.isoformat()
    result["details"]["last_ts"] = t1.isoformat()

    # Bars within the contract window
    in_window = [
        t for t in (datetime.fromisoformat(r.replace("Z", "+00:00")) for r in ts_raw)
        if WINDOW_START <= t <= WINDOW_END
    ]
    result["details"]["in_window_bars"] = len(in_window)

    if not in_window:
        result["status"] = "OUT_OF_WINDOW"
        return result

    # Contiguity + missing-tick rate over the contract window
    contig, n_months = month_spans(in_window)
    wd = count_weekdays(WINDOW_START, WINDOW_END)
    expected = wd * 1440
    missing_rate = 1.0 - (len(in_window) / expected) if expected else 1.0

    result["details"]["contiguous_months"] = contig
    result["details"]["months_present"] = n_months
    result["details"]["expected_bars_mon_weekdays"] = expected
    result["details"]["missing_tick_rate"] = round(missing_rate, 4)

    qualifies = (
        contig >= MIN_CONTIG_MONTHS
        and missing_rate < MAX_MISSING_TICK_RATE
    )
    result["details"]["qualifies"] = qualifies
    result["status"] = "QUALIFIES" if qualifies else "FAILS_CONTRACT"
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=",".join(UNIVERSE))
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    pairs = [p.lower() for p in args.pairs.split(",")]
    report = {"window": f"{WINDOW_START.isoformat()}..{WINDOW_END.isoformat()}",
              "contract": {"min_contiguous_months": MIN_CONTIG_MONTHS,
                           "max_missing_tick_rate": MAX_MISSING_TICK_RATE},
              "pairs": {}}

    for p in pairs:
        prior = PRIOR_DIR / f"{p.upper()}.json"
        ba = BA_DIR / f"{p.upper()}.json"
        # Prefer the prior archive (contract window), fall back to the ba archive.
        path = prior if prior.exists() else ba
        report["pairs"][p] = audit_pair(p, path)

    qualifying = [p for p, r in report["pairs"].items() if r["status"] == "QUALIFIES"]
    n_q = len(qualifying)

    if n_q < MIN_QUALIFYING:
        verdict = "DATA-UNAVAILABLE"
        verdict_note = "fewer than 4 qualifying pairs: no promotion analysis; per R6 shelved/labelled"
    elif n_q < FULL_UNIVERSE:
        verdict = "EXPLORATORY"
        verdict_note = "4-5 qualifying pairs: exploratory study only; no full-universe replication claim (R6)"
    else:
        verdict = "FULL"
        verdict_note = "6 qualifying pairs: full EXP-FX-002 analysis (R6)"

    report["qualifying_pairs"] = qualifying
    report["n_qualifying"] = n_q
    report["verdict"] = verdict
    report["verdict_note"] = verdict_note

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return

    print(f"EXP-FX-002 Step 0 audit — window {report['window']}")
    print(f"{'pair':8} {'status':16} {'bars_in_win':>11} {'contig_mo':>9} {'missing%':>8} {'dups':>5}")
    for p, r in report["pairs"].items():
        d = r["details"]
        print(f"{p:8} {r['status']:16} {d.get('in_window_bars', 0):11d} "
              f"{d.get('contiguous_months', 0):9d} "
              f"{d.get('missing_tick_rate', 1.0) * 100:7.2f}% {d.get('duplicate_timestamps', 0):5d}")
    print(f"\nQualifying pairs ({n_q}): {', '.join(qualifying) if qualifying else 'none'}")
    print(f"VERDICT: {verdict} — {verdict_note}")


if __name__ == "__main__":
    sys.exit(main())