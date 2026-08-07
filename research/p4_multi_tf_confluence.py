"""P4 (debated pivot Phase 1) — multi-TF confluence: 4H momentum gated by a
daily vol regime. The one structurally-untested FX axis (regime gating /
multi-TF confluence) per pivot-options.md.

FROZEN concept (no parameter tweaks — Decision C):
  Baseline: long 4H when close > 20-SMA(4H close).
  Gated:    the SAME 4H signal, entered ONLY when the 30-day realized daily
            vol (of the PREVIOUS completed day) > 50th percentile of the
            trailing ~150 daily-vol values. No same-day lookahead: the gate
            for 4H bar on day D uses daily closes strictly before day D.

Pre-registered kill criteria (ALL must pass on combined 2-fold OOS):
  1. Power:  combined OOS trades >= 60.
  2. Significance: gated beats ungated OOS Sharpe at 95% by 1000-iteration
     block bootstrap (block=5) on the per-bar return difference.
  3. Absolute: gated OOS annualized Sharpe >= 0.
  GBPUSD = OOS robustness only, never a promotion gate.

Costs: 0.8 pips round-trip (0.5 comm + 0.3 slip) -> 0.4 pips/side.
Sizing: fixed $100k notional.
Evidence-led, no fabrication, no promotion. Screen only.
"""
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research" / "dukascopy_1m_ba"
SMA_N = 20
VOL_WIN = 30
VOL_PCT_LOOK = 150
PCT_Q = 0.50
COST_SIDE = 0.4 * 0.0001          # 0.8 pips RT / 2
NOTIONAL = 100_000.0
BARS_PER_YEAR = 2190.0             # 4H calendar bars/yr
BOOT = 1000
BLOCK = 5
MIN_TRADES = 60


def load_pair(pair):
    """(closes_4h, day_of_4h) — closes and the calendar-day bucket per bar."""
    raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
    by4: dict[int, dict] = {}
    daymap: dict[str, int] = {}
    day_list: list[str] = []
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        c = b["c_bid"]
        day = dt.strftime("%Y-%m-%d")
        if day not in daymap:
            daymap[day] = len(day_list)
            day_list.append(day)
        key = int(dt.timestamp() // (4 * 3600))   # real 4h bucket
        if key not in by4:
            by4[key] = {"day": daymap[day], "close": c}
        else:
            by4[key]["close"] = c                  # last close in bucket
    keys = sorted(by4.keys())
    closes4 = [by4[k]["close"] for k in keys]
    days4 = [by4[k]["day"] for k in keys]
    return closes4, days4, day_list


def sma(series, n):
    if len(series) < n:
        return [None] * len(series)
    cum = [0.0]
    for c in series:
        cum.append(cum[-1] + c)
    out = [None] * len(series)
    for i in range(n - 1, len(series)):
        out[i] = (cum[i + 1] - cum[i + 1 - n]) / n
    return out


def daily_closes_from_bars(pair):
    """Daily closes (last close of each calendar day)."""
    raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
    byday: dict[str, list] = {}
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        byday.setdefault(dt.strftime("%Y-%m-%d"), []).append(b["c_bid"])
    return [vs[-1] for vs in byday.values()]


def daily_realized_vol(daycloses, win):
    """Daily realized vol series (std of last `win` daily log-returns)."""
    lr = [0.0] + [math.log(daycloses[i] / daycloses[i - 1]) for i in range(1, len(daycloses))]
    out = [None] * len(daycloses)
    for i in range(win, len(daycloses)):
        out[i] = statistics.pstdev(lr[i - win + 1:i + 1])
    return out


def gate_series(dvol, days4):
    """For each 4H bar (day d), gate = dvol[d-1] > 50th pct of dvol[max(0,d-151)..d-1].
    Uses only data before day d (strictly no same-day lookahead)."""
    out = [False] * len(days4)
    for i, d in enumerate(days4):
        if d <= 0 or dvol[d - 1] is None:
            continue
        lo = max(0, d - VOL_PCT_LOOK)
        win = [v for v in dvol[lo:d] if v is not None]
        if len(win) < VOL_PCT_LOOK // 2:
            continue
        thresh = sorted(win)[int(len(win) * PCT_Q)]
        out[i] = dvol[d - 1] > thresh
    return out


def run_strategy(closes4, fsma, gate, start, end, use_gate):
    """Long-only momentum on 4H bars [start:end) (OOS window). Returns
    (trades, per-bar returns, sharpe)."""
    n = len(closes4)
    pos = 0
    entry = 0.0
    trades = 0
    rets = []
    for i in range(max(start, 1), min(end, n)):
        sig = fsma[i] is not None and closes4[i] > fsma[i]
        want = sig and (gate[i] if use_gate else True)
        if want and pos == 0:
            entry = closes4[i]
            cash_side = -COST_SIDE * NOTIONAL
            pos = 1
            trades += 1
            rets.append(cash_side / NOTIONAL)
        elif not want and pos != 0:
            # close at this bar's close (approx), pay exit cost
            rets.append((closes4[i] - entry) / entry - COST_SIDE)
            pos = 0
        elif pos != 0:
            rets.append((closes4[i] - entry) / entry)
        else:
            rets.append(0.0)
    if pos != 0:
        # mark to last close, pay exit cost
        rets.append((closes4[min(end, n) - 1] - entry) / entry - COST_SIDE)
        pos = 0
        trades += 1
    sharpe = None
    if len(rets) >= 20 and statistics.stdev(rets) > 0:
        sharpe = (statistics.fmean(rets) / statistics.stdev(rets)) * math.sqrt(BARS_PER_YEAR)
    return {"trades": trades, "rets": rets, "sharpe": sharpe}


def block_bootstrap_diff(gated_rets, ungated_rets, iters=BOOT, block=BLOCK):
    """95% one-sided: is mean(gated - ungated) > 0? Block bootstrap on the
    aligned difference series. Returns (pct_025, pct_975, frac_positive)."""
    n = min(len(gated_rets), len(ungated_rets))
    d = [gated_rets[i] - ungated_rets[i] for i in range(n)]
    if len(d) < 20:
        return None
    means = []
    nblocks = max(len(d) // block, 1)
    for _ in range(iters):
        idx = []
        for _b in range(nblocks):
            start = np.random.randint(0, len(d) - block + 1) if len(d) >= block else 0
            idx.extend(range(start, min(start + block, len(d))))
        means.append(statistics.fmean(d[i] for i in idx[:len(d)]))
    means.sort()
    return (means[int(len(means) * 0.025)], means[int(len(means) * 0.975)],
            statistics.fmean([1.0 if m > 0 else 0.0 for m in means]))


def main():
    results = {}
    for pair in ("EURUSD", "GBPUSD"):
        closes4, days4, _ = load_pair(pair)
        fsma = sma(closes4, SMA_N)
        daycloses = daily_closes_from_bars(pair)
        dvol = daily_realized_vol(daycloses, VOL_WIN)
        gate = gate_series(dvol, days4)
        n = len(closes4)
        # anchored 2-fold OOS (frozen params — same as EXP-17 retest layout)
        folds = [(int(n * 0.60), int(n * 0.80)), (int(n * 0.80), n)]
        comb_ung, comb_gat = [], []
        tr_u = tr_g = 0
        for (a, b) in folds:
            ru = run_strategy(closes4, fsma, gate, a, b, use_gate=False)
            rg = run_strategy(closes4, fsma, gate, a, b, use_gate=True)
            tr_u += ru["trades"]; tr_g += rg["trades"]
            comb_ung += ru["rets"]; comb_gat += rg["rets"]
        s_u = (statistics.fmean(comb_ung) / statistics.stdev(comb_ung)) * math.sqrt(BARS_PER_YEAR) \
            if len(comb_ung) >= 20 and statistics.stdev(comb_ung) > 0 else None
        s_g = (statistics.fmean(comb_gat) / statistics.stdev(comb_gat)) * math.sqrt(BARS_PER_YEAR) \
            if len(comb_gat) >= 20 and statistics.stdev(comb_gat) > 0 else None
        bstr = block_bootstrap_diff(comb_gat, comb_ung)
        print(f"\n[{pair}] n4h={n} gate_on={sum(gate)}/{len(gate)} "
              f"trades ungated={tr_u} gated={tr_g}")
        print(f"  OOS Sharpe: ungated={s_u and round(s_u, 2)}  gated={s_g and round(s_g, 2)}")
        print(f"  bootstrap diff 95% CI={bstr and (round(bstr[0], 5), round(bstr[1], 5))} "
              f"frac>0={bstr and round(bstr[2], 3)}")
        power_ok = tr_g >= MIN_TRADES
        sig_ok = bstr is not None and bstr[0] > 0
        abs_ok = s_g is not None and s_g >= 0
        print(f"  KILL: power({power_ok}) sig({sig_ok}) absolute({abs_ok})")
        results[pair] = {"n4h": n, "gate_on": sum(gate),
                         "trades_ungated": tr_u, "trades_gated": tr_g,
                         "sharpe_ungated": s_u, "sharpe_gated": s_g,
                         "bootstrap_ci": bstr, "power_ok": power_ok,
                         "significance_ok": sig_ok, "absolute_ok": abs_ok,
                         "gated_is_robust_oos": s_g is not None and s_g >= 0}

    # EURUSD is the decision pair; GBPUSD robustness only.
    e = results.get("EURUSD")
    decision = "P4 PASS" if (e and e["power_ok"] and e["significance_ok"] and e["absolute_ok"]) \
        else "P4 FAIL"
    print(f"\n=== P4 DECISION: {decision} (EURUSD is the gate; GBPUSD robustness) ===")

    out = {"experiment": "P4_multi_tf_confluence", "decision": decision,
           "frozen": {"sma_n": SMA_N, "vol_win": VOL_WIN, "pct_look": VOL_PCT_LOOK,
                      "pct_q": PCT_Q, "cost_side_pips": 0.4},
           "kill_criteria": {"min_trades": MIN_TRADES, "bootstrap": BOOT,
                             "block": BLOCK},
           "results": results}
    res = ROOT / "research" / "results" / "P4_multi_tf_confluence.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {res}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)