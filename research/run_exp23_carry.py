#!/usr/bin/env python3
"""EXP-00023 — cross-sectional G10 carry trade (Lustig-Roussanov-Verdelhan /
Menkhoff et al. replication) on 8 years of daily FX + FRED policy rates.

Universe: 7 currencies vs USD with live rate series (EUR, GBP, JPY, AUD, CAD,
NOK; CHF/SEK/NZD excluded — FRED rate series discontinued).

At each month-end: rank by (policy rate - Fed rate) -> long top-3, short
bottom-3, hold 1 month. Spread = spot forward spread + accrual (mean rate
differential / 12). Pure-spot spread also reported (the UIP-violation test).

Run:  python research/run_exp23_carry.py
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "research" / "tws_daily"
FRED = Path(__file__).resolve().parents[1] / "research" / "fred"

# (symbol, quoted vs USD, FRED rate id)
PAIRS = [("EURUSD", True, "ECBDFR"), ("GBPUSD", True, "IRSTCI01GBM156N"),
         ("USDJPY", False, "IRSTCI01JPM156N"), ("AUDUSD", True, "IRSTCI01AUM156N"),
         ("USDCAD", False, "IRSTCI01CAM156N"), ("USDNOK", False, "IRSTCI01NOM156N")]
CURR = ["EUR", "GBP", "JPY", "AUD", "CAD", "NOK"]
COST_BPS = 10.0


def load_rates(rate_id: str) -> dict[str, float]:
    """month-end rate series {YYYY-MM-DD: rate}."""
    out = {}
    with open(FRED / f"{rate_id}.csv") as f:
        for row in csv.DictReader(f):
            d, v = row["observation_date"], row.get(rate_id, "")
            if v not in ("", "."):
                out[d] = float(v)
    return out


def month_end(series: dict[str, float]) -> dict[str, float]:
    """Keep the last observation of each calendar month, keyed by YYYY-MM."""
    out = {}
    for d, v in series.items():
        out[d[:7]] = v  # later entries in the same month overwrite (series ordered)
    return out


def load_fx(sym: str) -> dict[str, float]:
    rows = json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))
    return {b["timestamp"][:10]: float(b["close"]) for b in rows}


def main():
    print("═══ EXP-00023 — cross-sectional G10 carry (7 currencies, 8y) ═══")
    usd_rate = month_end(load_rates("DFF"))
    rates = {cur: month_end(load_rates(rid)) for (_, _, rid), cur in zip(PAIRS, CURR)}
    fx = {sym: load_fx(sym) for sym, _, _ in PAIRS}
    # monthly grid from FX dates
    fx_dates = sorted(set.intersection(*(set(fx[sym]) for sym, _, _ in PAIRS)))
    months = sorted({d[:7] for d in fx_dates})
    months = [m for m in months if m in usd_rate and all(m in rates[c] for c in CURR)]
    print(f"months with full data: {len(months)} ({months[0]} -> {months[-1]})")

    spreads, spot_spreads, accruals = [], [], []
    for mi, m in enumerate(months[:-1]):
        nxt = months[mi + 1]
        diffs = []
        for cur, (sym, base_q, _) in zip(CURR, PAIRS):
            diff = rates[cur][m] - usd_rate[m]
            diffs.append((diff, cur, sym, base_q))
        diffs.sort(key=lambda x: -x[0])
        top, bot = diffs[:3], diffs[-3:]
        # spot forward returns over the month (log, currency convention)
        def spot_ret(sym, base_q, m, nxt):
            d0 = [d for d in fx_dates if d[:7] == m][-1]
            d1 = [d for d in fx_dates if d[:7] == nxt][-1]
            r = math.log(fx[sym][d1] / fx[sym][d0])
            return r if base_q else -r
        s_top = sum(spot_ret(s, bq, m, nxt) for _, _, s, bq in top) / 3
        s_bot = sum(spot_ret(s, bq, m, nxt) for _, _, s, bq in bot) / 3
        # rates are in PERCENT: /100 converts to decimal, /12 to monthly
        a_top = sum(d for d, *_ in top) / 3 / 100 / 12
        a_bot = sum(d for d, *_ in bot) / 3 / 100 / 12
        spreads.append((s_top - s_bot) + (a_top - a_bot))
        spot_spreads.append(s_top - s_bot)
        accruals.append(a_top - a_bot)

    for name, series in (("total (spot+carry)", spreads), ("spot only (UIP viol.)", spot_spreads)):
        n = len(series)
        mean = sum(series) / n
        sd = statistics.stdev(series)
        t = mean / (sd / math.sqrt(n))
        wins = sum(1 for s in series if s > 0) / n
        cum, peak, mdd = 0.0, 0.0, 0.0
        for s in series:
            cum += s
            peak = max(peak, cum)
            mdd = min(mdd, cum - peak)
        print(f"\n{name}: {mean*100:+.2f}%/mo ({mean*12*100:+.1f}%/yr) | t={t:.2f} | "
              f"win {wins:.0%} | maxDD {mdd*100:.1f}%")
        print(f"  net of {COST_BPS:.0f}bps/leg: {(mean - COST_BPS/10000)*100:+.2f}%/mo")
    print(f"\navg monthly accrual spread: {sum(accruals)/len(accruals)*100:+.2f}%")
    print("\nInterpretation: positive significant total = carry works; positive spot")
    print("component = UIP violation (high-rate currencies appreciate, the anomaly).")


if __name__ == "__main__":
    main()
