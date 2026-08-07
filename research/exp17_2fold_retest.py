"""EXP-00017 2-fold anchored OOS re-test (debated plan Step 1, GATING).

Reproduces the promoted vol-clustering effect's construction exactly
(run_fx_experiments.py FX-002: realized vol over 20 bars -> forward 1h
|return|, Spearman IC) on the Dukascopy 1m->1h data, split into 2 anchored
folds. Pre-registered pass criterion (debated plan):
  Spearman IC >= 0.10 in BOTH folds, same sign in both, no fold < 0.05.

Result branches everything downstream (vol-regime sizing, new data, pivot).
Evidence-led, no fabrication, no promotion.
"""
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research" / "dukascopy_1m_ba"
BARS_PER_YEAR = 2190.0
MINUTES = 60  # 1h bars (EXP-17 native frequency)


def load_1h_closes(pair):
    raw = json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8"))
    rows = []
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        rows.append((int(dt.timestamp() // (MINUTES * 60)), b["c_bid"]))
    buckets = {}
    for k, c in rows:
        buckets.setdefault(k, []).append(c)
    return [vs[-1] for vs in buckets.values()]


def spearman(xs, ys):
    """Spearman rank correlation (both lists same length, no Nones)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 30:
        return None, 0
    xs_, ys_ = zip(*pairs)
    def ranks(vals):
        idx = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0] * len(vals)
        for rank, i in enumerate(idx):
            r[i] = rank
        return r
    rx = ranks(list(xs_))
    ry = ranks(list(ys_))
    n = len(rx)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    if vx == 0 or vy == 0:
        return None, n
    return cov / (vx * vy), n


def exp17_series(closes):
    """realized vol(20 bars) -> forward 1h |return| (EXP-00017 construction)."""
    lr = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    n = len(closes)
    feat = [None] * n
    for i in range(1, n):
        if i >= 20:
            feat[i] = statistics.stdev(lr[i - 20:i])
    target = [None] * n
    for i in range(n - 1):
        target[i] = abs(lr[i])  # forward 1h |ret| = |this bar's log return|
    return feat, target


def fold_ic(closes, a, b):
    feat, target = exp17_series(closes)
    ic, n = spearman(feat[a:b], target[a:b])
    return ic, n


def main():
    results = {}
    for pair in ("EURUSD", "GBPUSD"):
        closes = load_1h_closes(pair)
        n = len(closes)
        # anchored 2-fold: fold1 IS 0..60%, OOS 60..80%; fold2 IS 0..80%, OOS 80..100%
        oos1_a, oos1_b = int(n * 0.60), int(n * 0.80)
        oos2_a, oos2_b = int(n * 0.80), n
        ic1, n1 = fold_ic(closes, oos1_a, oos1_b)
        ic2, n2 = fold_ic(closes, oos2_a, oos2_b)
        print(f"[exp17-retest] {pair}: OOS1 IC={ic1:.3f} (n={n1}), OOS2 IC={ic2:.3f} (n={n2})")
        results[pair] = {"oos1_ic": round(ic1, 4) if ic1 else None,
                         "oos2_ic": round(ic2, 4) if ic2 else None,
                         "oos1_n": n1, "oos2_n": n2,
                         "bars": n}

    # Pre-registered criterion: IC>=0.10 both folds, same sign, none <0.05
    verdicts = {}
    for pair, r in results.items():
        i1, i2 = r["oos1_ic"], r["oos2_ic"]
        if i1 is None or i2 is None:
            verdicts[pair] = "INCONCLUSIVE"
        elif i1 >= 0.10 and i2 >= 0.10 and (i1 > 0) == (i2 > 0) and min(i1, i2) >= 0.05:
            verdicts[pair] = "PASS"
        else:
            verdicts[pair] = "FAIL"
        print(f"[exp17-retest] {pair} -> {verdicts[pair]}")

    out = {"experiment": "EXP-00017-RETEST", "protocol": "debated plan Step 1",
           "criterion": "Spearman IC>=0.10 both folds, same sign, none <0.05",
           "pairs": results, "verdicts": verdicts}
    res = ROOT / "research" / "results" / "EXP-00017_2fold_retest.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {res}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)