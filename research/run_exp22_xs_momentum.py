#!/usr/bin/env python3
"""EXP-00022 — cross-sectional currency momentum on the G10 basket (Menkhoff et
al. 2012 replication) using 8 years of daily data.

Universe: 9 currencies vs USD (EUR, GBP, JPY, CHF, CAD, SEK, NOK, AUD, NZD).
Convention: currency return vs USD = +dlog(XXXUSD) for EURUSD/GBPUSD/AUDUSD/
NZDUSD; -dlog(USDXXX) for USDJPY/USDCHF/USDCAD/USDSEK/USDNOK.

At each rebalance: rank by trailing L-day return -> long top tercile (3),
short bottom tercile (3) -> hold to next rebalance. Spread = mean(top)-mean(bot).

Run:  python research/run_exp22_xs_momentum.py
"""
import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "research" / "tws_daily"

# (symbol, quoted vs USD: True = XXXUSD, False = USDXXX)
PAIRS = [("EURUSD", True), ("GBPUSD", True), ("AUDUSD", True), ("NZDUSD", True),
         ("USDJPY", False), ("USDCHF", False), ("USDCAD", False),
         ("USDSEK", False), ("USDNOK", False)]
COST_BPS = 10.0  # conservative round trip per currency leg


def load(sym: str) -> list[dict]:
    return json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))


def main():
    print("═══ EXP-00022 — cross-sectional G10 currency momentum (8y daily) ═══")
    # align on common dates
    date_maps = {sym: {b["timestamp"][:10]: float(b["close"]) for b in load(sym)} for sym, _ in PAIRS}
    common = sorted(set.intersection(*(set(m) for m in date_maps.values())))
    print(f"common trading days: {len(common)} ({common[0]} -> {common[-1]})")

    n = len(common)
    # currency returns vs USD (log), rows = dates, cols = currencies
    cur_names = ["EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "SEK", "NOK"]
    rets: list[list[float]] = []
    for i in range(n):
        row = []
        for (sym, base_quoted), _ in zip(PAIRS, cur_names):
            c = date_maps[sym][common[i]]
            c_prev = date_maps[sym][common[i - 1]]
            r = math.log(c / c_prev)
            row.append(r if base_quoted else -r)
        rets.append(row)

    for lookback, label in ((21, "1m"), (63, "3m")):
        for rebal, rlabel in ((5, "weekly"), (21, "monthly")):
            spreads, dates = [], []
            t = lookback
            while t + rebal <= n:
                # trailing returns
                trail = []
                for k in range(9):
                    lr = sum(rets[t - lookback + j][k] for j in range(1, lookback + 1))
                    trail.append(lr)
                order = sorted(range(9), key=lambda k: -trail[k])
                top, bot = order[:3], order[-3:]
                # forward returns over the rebalance horizon
                fwd_top = sum(sum(rets[t + j][k] for j in range(rebal)) for k in top) / 3
                fwd_bot = sum(sum(rets[t + j][k] for j in range(rebal)) for k in bot) / 3
                spreads.append(fwd_top - fwd_bot)
                dates.append(common[t])
                t += rebal

            n_r = len(spreads)
            mean = sum(spreads) / n_r
            sd = statistics.stdev(spreads) if n_r > 1 else 0.0
            tstat = mean / (sd / math.sqrt(n_r)) if sd > 0 else 0.0
            wins = sum(1 for s in spreads if s > 0)
            ann = mean * (12 if rlabel == "monthly" else 52)
            net = mean - COST_BPS / 10000
            # max drawdown of cumulative net spread
            cum, peak, mdd = 0.0, 0.0, 0.0
            for s in spreads:
                cum += s - COST_BPS / 10000
                peak = max(peak, cum)
                mdd = min(mdd, cum - peak)
            print(f"\n{label} lookback, {rlabel} rebalance ({n_r} periods):")
            print(f"  gross spread {mean*100:+.2f}%/period ({ann*100:+.1f}%/yr) | "
                  f"t={tstat:.2f} | win {wins/n_r:.0%} | SD {sd*100:.2f}%")
            print(f"  net of {COST_BPS:.0f}bps/leg: {net*100:+.2f}%/period "
                  f"({(mean*12-COST_BPS/10000*12)*100:+.1f}%/yr ann) | maxDD {mdd*100:.1f}%")

    print("\nInterpretation: positive, significant net spreads = cross-sectional")
    print("currency momentum replicates on G10 2018-2026 (the literature's best FX")
    print("effect, which needs a basket — impossible with 2 pairs).")


if __name__ == "__main__":
    main()
