#!/usr/bin/env python3
"""EXP-00024 — COT leveraged-money positioning vs forward FX returns.

Hypothesis (contrarian): extreme net leveraged-money positioning in FX futures
reverts over the following month — top-quintile net-long currencies underperform
the bottom-quintile net-short currencies going forward.

Convention: currency return vs USD = +dlog(XXXUSD) / -dlog(USDXXX); net-long
futures = bullish the currency. Positive IC = momentum (positioning follows
through); negative IC = contrarian (extremes revert).

Run:  python research/run_exp24_cot.py
"""
import json
import math
import statistics
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "research" / "tws_daily"
COT = Path(__file__).resolve().parents[1] / "research" / "cot"

CCY_PAIRS = {  # ccy -> (pair symbol, quoted base-first?)
    "EUR": ("EURUSD", True), "GBP": ("GBPUSD", True), "JPY": ("USDJPY", False),
    "CHF": ("USDCHF", False), "CAD": ("USDCAD", False), "AUD": ("AUDUSD", True),
    "NZD": ("NZDUSD", True), "MXN": ("USDMXN", False),
}
HORIZON_DAYS = 20  # ~1 month forward


def load_fx(sym: str) -> dict[str, float]:
    rows = json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))
    return {b["timestamp"][:10]: float(b["close"]) for b in rows}


def main():
    print("═══ EXP-00024 — COT leveraged-money positioning → forward FX returns ═══")
    cot = json.loads((COT / "fx_cot.json").read_text(encoding="utf-8"))
    fx = {sym: load_fx(sym) for sym, _ in CCY_PAIRS.values()}

    # per-currency percentile of net positioning (full-sample, per contract)
    obs = []  # (ccy, date, net_pctile, fwd_ret_ccy)
    for ccy, rows in cot.items():
        pair, base_first = CCY_PAIRS.get(ccy, (None, None))
        if pair is None or not rows or pair not in fx:
            continue
        nets = sorted(r["net"] for r in rows)
        fxd = fx[pair]
        dates = sorted(fxd)
        for r in rows:
            d = r["date"]
            if d not in fxd:
                continue
            i = dates.index(d)
            j = i + HORIZON_DAYS
            if j >= len(dates):
                continue
            # net percentile 0..1 (full sample)
            pct = sum(1 for n in nets if n < r["net"]) / len(nets)
            ret = math.log(fxd[dates[j]] / fxd[d])
            if not base_first:
                ret = -ret
            obs.append((ccy, d, pct, ret))

    if not obs:
        print("no observations")
        return
    n = len(obs)
    print(f"observations: {n} (ccy-weeks across contracts)")

    # IC: spearman between percentile and forward return
    from titan.research.validator import compute_ic
    ic_all = compute_ic([o[2] for o in obs], [o[3] for o in obs])

    # quintile spread (contrarian if top<bottom)
    obs_sorted = sorted(obs, key=lambda o: o[2])
    q = n // 5
    top = [o[3] for o in obs_sorted[4 * q:]]
    bot = [o[3] for o in obs_sorted[:q]]
    mt, mb = sum(top) / len(top), sum(bot) / len(bot)
    spread = mt - mb
    sd = statistics.stdev([o[3] for o in obs])
    t = spread / (sd / math.sqrt(q))

    # per-currency
    print(f"\nIC (positioning pctile vs 1m fwd ccy return): {ic_all:+.4f}  "
          f"(+ = momentum, - = contrarian)")
    print(f"top-quintile (most net-long): {mt*100:+.2f}%/mo")
    print(f"bottom-quintile (most net-short): {mb*100:+.2f}%/mo")
    print(f"top-bottom spread: {spread*100:+.2f}%/mo (t={t:.2f})")
    print(f"net of 10bps: {(spread - 0.001)*100:+.2f}%/mo")
    print("\nper currency:")
    for ccy in sorted({o[0] for o in obs}):
        cobs = [o for o in obs if o[0] == ccy]
        cobs_s = sorted(cobs, key=lambda o: o[2])
        cq = len(cobs) // 5
        if cq < 20:
            print(f"  {ccy}: n={len(cobs)} (too few)")
            continue
        ct = sum(o[3] for o in cobs_s[4 * cq:]) / cq
        cb = sum(o[3] for o in cobs_s[:cq]) / cq
        cic = compute_ic([o[2] for o in cobs], [o[3] for o in cobs])
        print(f"  {ccy}: n={len(cobs)} IC={cic:+.4f} top={ct*100:+.2f}% bot={cb*100:+.2f}% "
              f"spread={(ct-cb)*100:+.2f}%/mo")


if __name__ == "__main__":
    main()
