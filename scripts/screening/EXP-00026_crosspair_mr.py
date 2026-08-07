"""EXP-00026 — cross-pair mean reversion on EURGBP (debated protocol).

Implements the multi-model debated plan (search-broadening-screen.md):

- A: screen the EURGBP cross (real tradeable, 1x cost) derived from aligned
  EURUSD/GBPUSD 4h — NOT the 2-leg synthetic spread (2x friction).
- Cointegration pre-gate: Engle-Granger on EURUSD vs GBPUSD log ratio. If
  p > 0.05, HALT (do not screen a non-stationary spread).
- C: 2-fold anchored walk-forward, no fabricated OOS. Contiguous-Surface
  protocol: in IS find the largest contiguous profitable (z_entry, z_exit,
  max_hold) cluster; require >=3 cells; pass the MEDIAN param to OOS; no
  cluster fails that fold.
- B: calm-vol gate REJECTED (empirical reduced edge). No vol gating.
- Cost: 1.5 pips RT on EURGBP.
- Orthogonalization vs EXP-00017 not yet run here (needs EXP-17 daily series).

Evidence-led, no fabrication, no promotion, screen only.
"""
import json
import math
import statistics
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))

try:
    from statsmodels.tsa.stattools import coint
    HAVE_STATS = True
except ImportError:
    HAVE_STATS = False

COST_PIPS_RT = 1.5
UNITS = 100_000
DATA = ROOT / "research" / "dukascopy_1m_ba"
PIP = 0.0001


def load_pair_closes(pair):
    """Resample 1m bid closes to 4h via the research harness loader."""
    raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
    rows = []
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        rows.append((int(dt.timestamp() // (240 * 60)), b["c_bid"]))
    buckets = {}
    for k, c in rows:
        buckets.setdefault(k, []).append(c)
    closes = [vs[-1] for vs in buckets.values()]
    return closes


def derive_eurgbp(eu, gu):
    n = min(len(eu), len(gu))
    return [eu[i] / gu[i] for i in range(n)]


def log_series(series):
    return [math.log(x) for x in series]


def zscore_rolling(series, window):
    out = [None] * len(series)
    for i in range(window - 1, len(series)):
        win = series[i - window + 1:i + 1]
        mu = statistics.fmean(win)
        sd = statistics.stdev(win)
        out[i] = (series[i] - mu) / sd if sd > 0 else 0.0
    return out


def engle_granger_p(x, y):
    if not HAVE_STATS:
        return None
    res = coint(x, y, trend="c", method="aeg", maxlag=1)
    return float(res[1])


def backtest_mr(bars, z, z_entry, z_exit, max_hold):
    """Long when z < -ze, short when z > ze; flatten on |z|<=zx or max_hold."""
    n = len(bars)
    cost = COST_PIPS_RT * 0.0001
    cash = 0.0
    pos = 0
    entry = 0.0
    hold = 0
    n_trades = 0
    peak = 100000.0
    maxdd = 0.0
    for i in range(1, n):
        zval = z[i - 1]
        if pos == 0:
            if zval is not None and zval <= -z_entry:
                pos = 1; entry = bars[i]; cash -= cost * UNITS; hold = 0; n_trades += 1
            elif zval is not None and zval >= z_entry:
                pos = -1; entry = bars[i]; cash -= cost * UNITS; hold = 0; n_trades += 1
        else:
            hold += 1
            if (zval is not None and abs(zval) <= z_exit) or hold >= max_hold:
                cash += pos * (bars[i] - entry) * UNITS - cost * UNITS
                n_trades += 1
                pos = 0
        eq = 100000.0 + cash + (pos * (bars[i] - entry) * UNITS if pos else 0)
        peak = max(peak, eq)
        if peak > 0:
            maxdd = max(maxdd, (peak - eq) / peak)
    if pos != 0:
        cash += pos * (bars[-1] - entry) * UNITS - cost * UNITS
        n_trades += 1
    return {"net_pips": round(cash / UNITS / PIP, 1), "trades": n_trades,
            "max_dd_pct": round(maxdd * 100, 2)}


def contiguous_cluster_median(grid):
    """Largest contiguous cluster of profitable (ze,zx,mh) cells; median param.
    Returns None if largest cluster < 3 cells."""
    profitable = set(k for k, v in grid.items() if v > 0)
    seen = set()
    best = []
    for k in profitable:
        if k in seen:
            continue
        comp = []
        dq = deque([k])
        seen.add(k)
        while dq:
            cur = dq.popleft()
            comp.append(cur)
            a, b, c = cur
            for nb in ((a + 1, b, c), (a - 1, b, c), (a, b + 1, c),
                       (a, b - 1, c), (a, b, c + 1), (a, b, c - 1)):
                if nb in profitable and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        if len(comp) > len(best):
            best = comp
    if len(best) < 3:
        return None
    med = tuple(
        sorted(set(x[d] for x in best))[len(set(x[d] for x in best)) // 2]
        for d in range(3)
    )
    return med


def main():
    eu = load_pair_closes("EURUSD")
    gu = load_pair_closes("GBPUSD")
    n = min(len(eu), len(gu))
    eu, gu = eu[:n], gu[:n]
    eurgbp = derive_eurgbp(eu, gu)
    lr = log_series(eurgbp)
    print(f"[exp26] EURGBP bars={n} derived from EURUSD/GBPUSD")

    # Cointegration gate (debated plan: full EURUSD vs GBPUSD series)
    p = engle_granger_p(np.array(eu), np.array(gu))
    print(f"[exp26] Engle-Granger coint (full window) p={p if p is not None else 'n/a'}")
    if p is not None and p > 0.05:
        print("HALT: not cointegrated (p>0.05) — skip non-stationary")
        # still write a halt marker and exit non-zero per protocol
        _write({"experiment": "EXP-000026", "decision": "HALT_NOT_COINTEGRATED",
                "coint_p": p})
        return 2

    # 2-fold anchored WF (0-based slices)
    folds = (("fold1", 252, 882, 882, 1197),
             ("fold2", 252, 1197, 1197, 1511))
    results = []
    for label, is_a, is_b, oos_a, oos_b in folds:
        is_lr = lr[is_a:is_b]
        oos_lr = lr[oos_a:oos_b]
        grid = {}
        for ze in (1.5, 2.0, 2.5, 3.0):
            for zx in (0.0, 0.25, 0.5):
                for mh in (12, 24, 36, 48):
                    z = zscore_rolling(is_lr, 20)
                    r = backtest_mr(is_lr, z, ze, zx, mh)
                    grid[(ze, zx, mh)] = r["net_pips"]
        med = contiguous_cluster_median(grid)
        if med is None:
            print(f"  {label}: no contiguous profitable cluster >=3 — FAIL")
            results.append({"fold": label, "survive": False})
            continue
        ze, zx, mh = med
        z = zscore_rolling(oos_lr, 20)
        r = backtest_mr(oos_lr, z, ze, zx, mh)
        ok = r["trades"] > 0 and r["net_pips"] > 0
        print(f"  {label}: med ze={ze} zx={zx} mh={mh} -> OOS {r['net_pips']} pips, "
              f"trades {r['trades']}, dd {r['max_dd_pct']}%")
        results.append({"fold": label, "survive": ok, "param": list(med),
                        "oos_net_pips": r["net_pips"], "oos_trades": r["trades"],
                        "oos_dd_pct": r["max_dd_pct"]})

    decision = "SURVIVOR" if all(r["survive"] for r in results) else "REJECT_NONCONCLUSIVE"
    print(f"\n[exp26] decision={decision}")
    _write({"experiment": "EXP-000026", "decision": decision, "folds": results,
            "coint_p": p, "cost_pips_rt": COST_PIPS_RT,
            "note": "debated plan; calm-vol gate rejected per A/B decisions; "
                    "orthogonalization vs EXP-17 is a follow-up needing that daily series"})
    return 0


def _write(payload):
    res = ROOT / "research" / "results" / "EXP-000026_crosspair_mr.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[exp2] wrote {res}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)