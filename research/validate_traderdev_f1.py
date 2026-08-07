#!/usr/bin/env python3
"""EXP-00025 follow-up — combine the surviving F1 (EMA9×VWAP trailing) with the
PROMOTED vol-clustering regime gate (EXP-00017) and test for robustness.

F1 is the only trader.dev family that nets positive on both pairs @4h, but it
failed quarterly stability on EURUSD (2/4). TITAN's own research showed vol
*clustering* (not vol level) is the one robust FX effect. Test: does gating F1
signals on elevated-vs-median trailing vol make the edge cross-instrument and
quarter-stable, i.e. clear the promotion gate?
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import run_traderdev_families as m
from run_traderdev_families import DATA, load, F1_EMA9VWAP, QTY, PIP


def log_vol(rows, lookback):
    out = [0.0] * len(rows)
    for i in range(len(rows)):
        lo = max(0, i - lookback + 1)
        rets = []
        for k in range(lo + 1, i + 1):
            rets.append(math.log(rows[k]["c_bid"] / rows[k - 1]["c_bid"]))
        if len(rets) >= 2:
            mu = sum(rets) / len(rets)
            out[i] = math.sqrt(sum((x - mu) ** 2 for x in rets) / len(rets))
    return out


def make_gated(F, vol_lookback, newest=True, drop_med_ratio=1.0):
    class GF(F):
        def __init__(self, rows):
            self.vlb = vol_lookback
            super().__init__(rows)
        def prep(self):
            super().prep()
            v = log_vol(self.rows, self.vlb)
            self._v = v
            self._vmed = [0.0] * len(v)
            for i in range(len(v)):
                lo = max(0, i - 2 * self.vlb)
                seg = sorted(v[lo:i + 1])
                if seg:
                    self._vmed[i] = seg[len(seg) // 2]
        def signal(self, i):
            side, levels = super().signal(i)
            if side is None:
                return None, {}
            # regime gate: current vol vs trailing median
            if self._v[i] <= self._vmed[i]:
                return None, {}
            return side, levels
    return GF


def main():
    print("=" * 70)
    print("EXP-00025 follow-up — F1 4h + vol-regime gate (blocks low-vol entries)")
    print("=" * 70)
    for pair in ["EURUSD", "GBPUSD"]:
        raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
        rows = load(raw, 240)
        n = len(rows)

        base = m.F1_EMA9VWAP(rows).run()
        print(f"\n{pair} 4h  (n={n} bars)")
        print(f"  BASE           net={base['net_pips']:+8.1f} pips  {base['trades']:>3} trades")

        for lb in (40, 80, 168):
            GF = make_gated(m.F1_EMA9VWAP, lb)
            r = GF(rows).run()
            # quarterly stability
            q = n // 4
            qp = []
            for k in range(4):
                seg = rows[k * q:(k + 1) * q if k < 3 else n]
                qr = GF(seg).run()
                qp.append(qr["net_pips"])
            pos = sum(1 for p in qp if p > 0)
            print(f"  vol-gate LB={lb:<3} : net={r['net_pips']:+8.1f} pips  {r['trades']:>3} tr  "
                  f"quarters=[{','.join(f'{p:+6.1f}' for p in qp)}] pos={pos}/4")

    # pooled gate vs base
    print("\nPOOLED (EURUSD+GBPUSD @ 4h):")
    base_tot = 0.0
    for pair in ["EURUSD", "GBPUSD"]:
        raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
        rows = load(raw, 240)
        base_tot += m.F1_EMA9VWAP(rows).run()["net_pips"]
    print(f"  BASE total: {base_tot:+8.1f} pips")
    for lb in (40, 168):
        GF = make_gated(m.F1_EMA9VWAP, lb)
        tot = 0.0; tr = 0
        for pair in ["EURUSD", "GBPUSD"]:
            raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
            rows = load(raw, 240)
            r = GF(rows).run()
            tot += r["net_pips"]; tr += r["trades"]
        print(f"  GATE LB={lb:<3} total: {tot:+8.1f} pips  {tr} trades")


if __name__ == "__main__":
    main()