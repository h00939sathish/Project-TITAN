#!/usr/bin/env python3
"""EXP-00019 economics on real bid/ask data (dukascopy_1m_ba_v1).

Replaces the assumed 1.0-pip round trip with ACTUAL spreads: for each bar the
reversal signal (negative of trailing 12h mid return) is quintiled; the top
quintile is traded SHORT (sell at bid, buy back at ask) and the bottom quintile
LONG (buy at ask, sell at bid), 1h hold. Net pips include the real spread.

Run:  python research/run_exp19_costs.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "research" / "dukascopy_1m_ba"


def load(sym: str) -> list[dict]:
    return json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))


def mid(b: dict) -> float:
    return (b["c_ask"] + b["c_bid"]) / 2


def reverse_quintiles(bars: list[dict], overlap_only: bool) -> dict:
    """Signal = -(12h mid return); target = next-1h mid return. Real-cost P&L."""
    mids = [mid(b) for b in bars]
    n = len(bars)
    lookback, horizon = 720, 60  # 12h / 1h at 1-min
    rows = []
    for i in range(lookback, n - horizon):
        if overlap_only and not (12 <= int(bars[i]["timestamp"][11:13]) <= 15):
            continue
        sig = -(mids[i] / mids[i - lookback] - 1.0)
        fwd_mid = mids[i + horizon] / mids[i] - 1.0
        rows.append((sig, fwd_mid, i))

    rows.sort(key=lambda r: r[0])
    q = len(rows) // 5
    if q < 10:
        return {"n": 0}
    res = {"n": len(rows)}
    gross, net = [], []
    for qi in range(5):
        chunk = rows[qi * q:(qi + 1) * q]
        g = sum(r[1] for r in chunk) / len(chunk) * 10000
        gross.append(g)
        # real-cost P&L with CORRECT legs: Q1 (biggest 12h RALLY, reversal says
        # pull back) -> SHORT (sell bid, buy back ask); Q5 (biggest DROP,
        # reversal says bounce) -> LONG (buy ask, sell bid).
        if qi == 0:
            pnl = sum(
                (bars[r[2]]["c_bid"] - mid(bars[r[2] + horizon])) / bars[r[2]]["c_bid"]
                for r in chunk
            ) / len(chunk) * 10000
        elif qi == 4:
            pnl = sum(
                (mid(bars[r[2] + horizon]) - bars[r[2]]["c_ask"]) / bars[r[2]]["c_ask"]
                for r in chunk
            ) / len(chunk) * 10000
        else:
            pnl = None
        net.append(pnl)
    res["quintile_gross"] = gross
    res["spread_top_bottom"] = gross[4] - gross[0]
    res["net_short_top"] = net[4]
    res["net_long_bottom"] = net[0]
    res["net_top_bottom"] = ((net[4] or 0) - (net[0] or 0)) / 2  # average of both legs
    return res


def main():
    print("EXP-00019 real-cost economics (dukascopy_1m_ba_v1, 1-min bars, 12h->1h reversal)")
    print("=" * 92)
    print(f"{'':6}{'n':>8}{'Q1':>8}{'Q5':>8}{'gross TB':>10}{'net longQ1':>11}{'net shortQ5':>12}{'net TB':>9}")
    for sym in ("EURUSD", "GBPUSD"):
        bars = load(sym)
        for label, ov in (("full-day", False), ("12-16UTC", True)):
            r = reverse_quintiles(bars, ov)
            if r.get("n", 0) < 100:
                print(f"{sym:<6}{label:>6}: insufficient sample")
                continue
            g = r["quintile_gross"]
            print(f"{sym:<6}{label:>6}{r['n']:>8}{g[0]:>8.2f}{g[4]:>8.2f}"
                  f"{r['spread_top_bottom']:>10.2f}{r['net_long_bottom']:>11.2f}"
                  f"{r['net_short_top']:>12.2f}{r['net_top_bottom']:>9.2f}")
    print("\nAll figures in pips (1h hold, real ask/bid execution, no slippage).")
    print("net TB > 0 means the reversal pays the real spread on average across both legs.")


if __name__ == "__main__":
    main()
