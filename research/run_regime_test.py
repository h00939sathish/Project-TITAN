#!/usr/bin/env python3
"""Regime test — rerun TSM / cross-sectional momentum / carry on 27 years of
daily data (FRED H.10 FX + FRED policy rates), split pre-2010 vs post-2010.

Answers: were the literature effects present in the golden era (1999-2009) and
did they die after (2010-2025)? Same code paths as EXP-00021/22/23.

Run:  python research/run_regime_test.py
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "research" / "tws_daily"
FRED = Path(__file__).resolve().parents[1] / "research" / "fred"

PAIRS = [("EURUSD", True), ("GBPUSD", True), ("AUDUSD", True), ("NZDUSD", True),
         ("USDJPY", False), ("USDCHF", False), ("USDCAD", False),
         ("USDSEK", False), ("USDNOK", False)]
CURR = ["EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "SEK", "NOK"]
RATE_IDS = {"EUR": "IRSTCI01EZM156N", "GBP": "IRSTCI01GBM156N", "JPY": "IRSTCI01JPM156N",
            "AUD": "IRSTCI01AUM156N", "CAD": "IRSTCI01CAM156N", "NOK": "IRSTCI01NOM156N",
            "CHF": "IRSTCI01CHM156N", "SEK": "IRSTCI01SEM156N", "NZD": "IRSTCI01NZM156N"}
COST_BPS = 10.0
WINDOWS = [("1999-2009 (pre-2010)", 1999, 2009), ("2010-2025 (post-2010)", 2010, 2025)]


def load_fx(sym: str) -> dict[str, float]:
    rows = json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))
    return {b["timestamp"][:10]: float(b["close"]) for b in rows}


def month_end(series: dict[str, float]) -> dict[str, float]:
    out = {}
    for d, v in series.items():
        out[d[:7]] = v
    return out


def load_rates(rid: str) -> dict[str, float]:
    out = {}
    with open(FRED / f"{rid}.csv") as f:
        for row in csv.DictReader(f):
            v = row.get(rid, "")
            if v not in ("", "."):
                out[row["observation_date"]] = float(v)
    return out


def slice_window(fx: dict[str, float], y0: int, y1: int) -> dict[str, float]:
    return {d: v for d, v in fx.items() if y0 <= int(d[:4]) <= y1}


def tsm_test(fx_eur: dict, fx_gbp: dict, y0: int, y1: int) -> None:
    """EXP-00021R: TSM IC grid on EURUSD/GBPUSD."""
    from titan.research.validator import compute_ic

    print(f"\n  TSM (EURUSD/GBPUSD {y0}-{y1}):")
    for lb in (21, 63, 126, 252):
        ics = []
        for fx in (fx_eur, fx_gbp):
            dates = sorted(d for d in fx if y0 <= int(d[:4]) <= y1)
            closes = [fx[d] for d in dates]
            sigs, tgts = [], []
            for i in range(lb, len(closes)):
                if i + 63 < len(closes):
                    sigs.append(closes[i] / closes[i - lb] - 1.0)
                    tgts.append(closes[i + 63] / closes[i] - 1.0)
            ics.append(compute_ic(sigs, tgts) if len(sigs) >= 30 else 0.0)
        print(f"    lb={lb:>3} (fwd 63d): EUR IC={ics[0]:+.4f}  GBP IC={ics[1]:+.4f}")


def xs_momentum(fx_map: dict[str, dict], y0: int, y1: int) -> None:
    """EXP-00022R: 9-currency cross-sectional momentum, 1m/weekly + 3m/monthly."""
    print(f"\n  XS momentum (9 currencies {y0}-{y1}):")
    common = sorted(set.intersection(*(set(slice_window(fx, y0, y1)) for fx in fx_map.values())))
    if len(common) < 250:
        print("    insufficient data")
        return
    # currency returns vs USD
    rets = []
    for i in range(len(common)):
        row = []
        for (sym, base_q) in PAIRS:
            c = fx_map[sym][common[i]]
            cp = fx_map[sym][common[i - 1]]
            r = math.log(c / cp)
            row.append(r if base_q else -r)
        rets.append(row)
    for lb, rebal, label in ((21, 5, "1m lookback / weekly"), (63, 21, "3m lookback / monthly")):
        spreads = []
        t = lb
        while t + rebal <= len(common):
            trail = [sum(rets[t - lb + j][k] for j in range(1, lb + 1)) for k in range(9)]
            order = sorted(range(9), key=lambda k: -trail[k])
            top, bot = order[:3], order[-3:]
            ft = sum(sum(rets[t + j][k] for j in range(rebal)) for k in top) / 3
            fb = sum(sum(rets[t + j][k] for j in range(rebal)) for k in bot) / 3
            spreads.append(ft - fb)
            t += rebal
        n = len(spreads)
        mean = sum(spreads) / n
        sd = statistics.stdev(spreads)
        tstat = mean / (sd / math.sqrt(n))
        net = mean - COST_BPS / 10000
        print(f"    {label}: {mean*100:+.2f}%/period (t={tstat:.2f}) net {net*100:+.2f}% | n={n}")


def carry(fx_map: dict[str, dict], y0: int, y1: int) -> None:
    """EXP-00023R: 7-currency carry vs USD."""
    print(f"\n  Carry (7 currencies {y0}-{y1}):")
    usd_rate = month_end(load_rates("DFF"))
    rates = {c: month_end(load_rates(RATE_IDS[c])) for c in ("EUR", "GBP", "JPY", "AUD", "CAD", "NOK")}
    cur_list = ["EUR", "GBP", "JPY", "AUD", "CAD", "NOK"]
    pairs7 = [("EURUSD", True), ("GBPUSD", True), ("USDJPY", False),
              ("AUDUSD", True), ("USDCAD", False), ("USDNOK", False)]
    common = sorted(set.intersection(*(set(slice_window(fx_map[s], y0, y1)) for s, _ in pairs7)))
    months = sorted({d[:7] for d in common})
    months = [m for m in months if m in usd_rate and all(m in rates[c] for c in cur_list)]
    spreads, spots = [], []
    for mi, m in enumerate(months[:-1]):
        nxt = months[mi + 1]
        diffs = sorted([(rates[c][m] - usd_rate[m], c, s, bq)
                        for c, (s, bq) in zip(cur_list, pairs7)], key=lambda x: -x[0])
        top, bot = diffs[:3], diffs[-3:]
        def spot(sym, bq):
            d0 = [d for d in common if d[:7] == m][-1]
            d1 = [d for d in common if d[:7] == nxt][-1]
            r = math.log(fx_map[sym][d1] / fx_map[sym][d0])
            return r if bq else -r
        st = sum(spot(s, bq) for _, _, s, bq in top) / 3
        sb = sum(spot(s, bq) for _, _, s, bq in bot) / 3
        at = sum(d for d, *_ in top) / 3 / 100 / 12
        ab = sum(d for d, *_ in bot) / 3 / 100 / 12
        spreads.append((st - sb) + (at - ab))
        spots.append(st - sb)
    for name, series in (("total", spreads), ("spot", spots)):
        n = len(series)
        if n < 24:
            print(f"    {name}: insufficient ({n} months)")
            continue
        mean = sum(series) / n
        sd = statistics.stdev(series)
        t = mean / (sd / math.sqrt(n))
        print(f"    {name}: {mean*100:+.2f}%/mo (t={t:.2f}) net {(mean-COST_BPS/10000)*100:+.2f}% | n={n}")


def main():
    print("═══ REGIME TEST — 27y FRED daily FX, pre/post-2010 split ═══")
    fx_map = {sym: load_fx(sym) for sym, _ in PAIRS}
    for name, y0, y1 in WINDOWS:
        print(f"\n### {name}")
        tsm_test(fx_map["EURUSD"], fx_map["GBPUSD"], y0, y1)
        xs_momentum(fx_map, y0, y1)
        carry(fx_map, y0, y1)


if __name__ == "__main__":
    main()
