"""P2 — Macro-Momentum on spot gold (debated). Frozen signal, cost-aware.

FROZEN signal (pivot-options P2; zero overlap with failed FX axis):
  Driver 1 (real yields):  d1 = -sign(delta DFII10 over 252d)  [falling real
                           yields => bullish gold]
  Driver 2 (commodities):  d2 = +sign(return DBC over 252d)    [rising
                           commodities => bullish gold]
  Combined: long gold when (d1 + d2) > 0, else flat. NO gold-price signal.

Frozen kill criteria (anchored 2-fold OOS on 2007-01..2023-12; Decision D):
  1. net annualized return > 4.0%
  2. OOS Sharpe > 0.45
  3. profit factor > 1.20
  4. max OOS drawdown < 20% at 10% ann. vol target
Cost: 1.0 bps RT, long-only (ADR-015: gold no shorting).

Data: gold GC=F (research/gold_assets/xauusd_daily.json), DBC (dbc_daily.json),
DFII10 (research/fred/DFII10.csv — official Treasury). Evidence-led, no lying.
"""
import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BARS_PER_YEAR = 252.0
LOOK = 252
COST = 0.0001  # 1.0 bps
TARGET_VOL = 0.10
EST_VOL = 0.12  # gold ann vol roughly, for scaling

# ---------- loading ----------

def _load_json_daily(path):
    rows = json.loads(Path(path).read_text())
    dates = [datetime.fromisoformat(r["date"]).date() for r in rows]
    vals = [float(r["close"]) for r in rows]
    return dates, vals


def _load_fred(series_id="DFII10"):
    p = ROOT / "research" / "fred" / f"{series_id}.csv"
    with open(p, newline="") as f:
        rows = [(r["observation_date"], r[series_id]) for r in csv.DictReader(f)]
    dates = [datetime.fromisoformat(d).date() for d, _ in rows]
    return dates, [float(v) for _, v in rows]


# ---------- align ----------

def align_multi(series):
    """series: list of (dates, vals). Union dates, ffill each column."""
    alld = sorted(set().union(*[set(d) for d, _ in series]))
    cols = []
    for dates, vals in series:
        col, cur, j = [], None, 0
        for d in alld:
            while j < len(dates) and dates[j] <= d:
                cur = vals[j]; j += 1
            col.append(cur)
        cols.append(col)
    return alld, cols


def sign_252(series):
    out = [None] * len(series)
    for i in range(LOOK, len(series)):
        if series[i] is None or series[i - LOOK] is None:
            continue
        out[i] = 1.0 if series[i] > series[i - LOOK] else -1.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2007-01-01")
    ap.add_argument("--end", default="2023-12-31")
    args = ap.parse_args()

    gold_d, gold = _load_json_daily(ROOT / "research/gold_assets/xauusd_daily.json")
    dbc_d, dbc = _load_json_daily(ROOT / "research/gold_assets/dbc_daily.json")
    dfii_d, dfii = _load_fred("DFII10")
    alldates, (gold_a, dbc_a, dfii_a) = align_multi([(gold_d, gold), (dbc_d, dbc), (dfii_d, dfii)])
    print(f"aligned: {len(alldates)} days {alldates[0]}..{alldates[-1]}")

    # signals
    d2 = sign_252(dbc_a)
    d1_raw = sign_252(dfii_a)
    d1 = [(-s if s is not None else None) for s in d1_raw]
    signal = [1.0 if (a is not None and b is not None and (a + b) > 0) else 0.0
              for a, b in zip(d1, d2)]

    # gold log returns (vol scaling not needed for direction test)
    gold_r = [0.0] * len(alldates)
    for i in range(1, len(alldates)):
        if gold_a[i] and gold_a[i - 1]:
            gold_r[i] = (gold_a[i] / gold_a[i - 1] - 1.0) * (TARGET_VOL / EST_VOL)
        else:
            gold_r[i] = 0.0

    # -- FROZEN eval window (debate Decision D: 2007-01..2023-12) --
    import datetime as _dt
    w_start = _dt.date.fromisoformat(args.start)
    w_end = _dt.date.fromisoformat(args.end)
    in_window = [w_start <= d <= w_end for d in alldates]

    # backtest: long when signal==1 else flat; 1.0bps RT each entry/exit
    n = len(alldates)
    rets = [0.0] * n
    pos = 0
    for i in range(1, n):
        if not in_window[i]:
            continue
        sig = 1 if (signal[i] is not None and signal[i]) else 0
        if sig and not pos:
            pos = 1
            rets[i] = gold_r[i] - COST
        elif not sig and pos:
            pos = 0
            rets[i] = gold_r[i] - COST
        elif pos:
            rets[i] = gold_r[i]
        else:
            rets[i] = 0.0

    # restrict to the frozen window first, then anchored 2-fold OOS (60-100%)
    win_rets = [r for r, w in zip(rets, in_window) if w]
    n_use = len(win_rets)
    folds = [(int(n_use * 0.60), int(n_use * 0.80)), (int(n_use * 0.80), n_use)]
    oos_rets = []
    for a, b in folds:
        oos_rets += win_rets[a:b]
    mu = statistics.fmean(oos_rets)
    sd = statistics.stdev(oos_rets)
    sharpe = (mu / sd) * math.sqrt(BARS_PER_YEAR) if sd > 0 else 0.0
    ann_ret = mu * BARS_PER_YEAR

    # profit factor & drawdown on OOS
    g = sum(x for x in oos_rets if x > 0)
    l = -sum(x for x in oos_rets if x < 0)
    pf = (g / l) if l > 0 else float("inf")
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for x in oos_rets:
        eq *= (1 + x)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)

    print(f"\nOOS (60-100%): ann_ret={ann_ret:.2%} Sharpe={sharpe:.2f} "
          f"PF={pf:.2f} maxDD={mdd:.2%} bars={len(oos_rets)}")
    ok = [ann_ret > 0.04, sharpe > 0.45, pf > 1.20, mdd < 0.20]
    names = ["ann>4%", "Sharpe>0.45", "PF>1.2", "DD<20%"]
    for k, v in zip(names, ok):
        print(f"  {k}: {v}")
    decision = "P2 PASS" if all(ok) else "P2 FAIL"
    print("=== P2 DECISION:", decision, "===")

    out = {"experiment": "P2_macro_momentum_gold", "decision": decision,
           "oos": {"ann_ret": round(ann_ret, 4), "sharpe": round(sharpe, 3),
                   "profit_factor": round(pf, 3), "max_dd": round(mdd, 4)},
           "kill": dict(zip(names, ok))}
    res = ROOT / "research" / "results" / "P2_macro_momentum_gold.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", res)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)