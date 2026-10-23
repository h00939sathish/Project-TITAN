#!/usr/bin/env python3
"""CRYPTO-007 — maker-rebate fee-regime feasibility, derived from the sealed
CRYPTO-006 in-sample artefact. No new market data, no OOS partition.

Frozen protocol: research/crypto/hypotheses/CRYPTO-007-prereg.json

Load-bearing logic: net_edge(fee f) = half_spread - f + markout, so the fee
shifts the whole per-fill distribution rigidly and each symbol's break-even
fee is exact. Rebate tiers are earned by 30-day volume, and venue schedules are
monotone non-increasing in volume. If the symbols demanding the deepest fee cut
are the ones able to generate the least volume, no monotone schedule can satisfy
them simultaneously -- a disproof that needs no tier table.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "research/crypto/results/CRYPTO-006-probe.json"
OUT = REPO / "research/crypto/results/CRYPTO-007-rebate-feasibility.json"

VIP0_FEE_BPS = 2.0
PARTICIPATION_CAP = 0.02
DAYS_90_TO_30 = 3.0
R1_MIN_FRACTION = 0.50
R2_CORR_THRESHOLD = -0.50
R3_VOLUME_MULTIPLE = 2.0
FEE_SWEEP_BPS = [2.0, 1.5, 1.0, 0.5, 0.0, -0.5, -1.0, -2.0]


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den if den else float("nan")


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, idx in enumerate(order):
            r[idx] = float(pos)
        return r

    return pearson(ranks(xs), ranks(ys))


def main() -> int:
    if not BUNDLE.exists():
        print(f"missing sealed bundle: {BUNDLE}", file=sys.stderr)
        return 1
    bundle = json.loads(BUNDLE.read_text())
    syms = bundle["symbols"]
    vol90 = {k: float(v) for k, v in bundle["universe"]["volume_90d_usd"].items()}

    med_vol = statistics.median(vol90[s] for s in syms if s in vol90)

    rows: dict[str, dict] = {}
    for s, v in syms.items():
        if s not in vol90:
            continue
        lb = v["bootstrap_lb95_net_bps"]
        # rigid shift: gross term = net observed at VIP0 + VIP0 fee
        f_be_median = v["median_net_edge_bps"] + VIP0_FEE_BPS
        f_be_lb95 = (lb + VIP0_FEE_BPS) if lb is not None else None
        max_vol_30d = PARTICIPATION_CAP * (vol90[s] / DAYS_90_TO_30)
        rows[s] = {
            "volume_90d_usd": vol90[s],
            "max_attainable_30d_volume_usd": round(max_vol_30d, 2),
            "f_be_median_bps": round(f_be_median, 4),
            "f_be_lb95_bps": round(f_be_lb95, 4) if f_be_lb95 is not None else None,
            "depth_capable": vol90[s] >= R3_VOLUME_MULTIPLE * med_vol,
            "positive_at_zero_fee": f_be_median > 0,
        }

    names = sorted(rows)
    fbe = [rows[s]["f_be_lb95_bps"] for s in names if rows[s]["f_be_lb95_bps"] is not None]
    vols = [rows[s]["max_attainable_30d_volume_usd"] for s in names
            if rows[s]["f_be_lb95_bps"] is not None]
    corr_pearson = pearson(fbe, vols)
    corr_spearman = spearman(fbe, vols)

    # schedule-free sweep: how many symbols turn LB95-positive at each fee
    sweep = {}
    for f in FEE_SWEEP_BPS:
        cnt = sum(1 for s in names
                  if rows[s]["f_be_lb95_bps"] is not None and rows[s]["f_be_lb95_bps"] > f)
        deep = sum(1 for s in names
                   if rows[s]["f_be_lb95_bps"] is not None and rows[s]["f_be_lb95_bps"] > f
                   and rows[s]["depth_capable"])
        sweep[f"{f:+.1f}"] = {"symbols_lb95_positive": cnt, "of_which_depth_capable": deep}

    r1_frac = sum(1 for s in names if rows[s]["positive_at_zero_fee"]) / len(names)
    r1 = r1_frac >= R1_MIN_FRACTION
    r2 = corr_pearson <= R2_CORR_THRESHOLD
    r3_any = [s for s in names if rows[s]["depth_capable"]
              and (rows[s]["f_be_lb95_bps"] or -99) > 0]
    r3 = bool(r3_any)

    gates = {
        "R1_fraction_positive_gross_at_zero_fee": round(r1_frac, 4),
        "R1_pass": r1,
        "R2_pearson_fbe_vs_attainable_volume": round(corr_pearson, 4),
        "R2_spearman": round(corr_spearman, 4),
        "R2_structural_anticorrelation_present": r2,
        "R3_depth_capable_symbols_recoverable": r3_any,
        "R3_pass": r3,
    }

    if not r1:
        verdict = "REBATE_REGIME_IMPOSSIBLE_GROSS_NEGATIVE"
    elif r2 and not r3:
        verdict = "REBATE_ATTAINMENT_CONTRADICTION"
    elif r2 and r3:
        verdict = "NO_STRUCTURAL_CONTRADICTION_VERIFY_SCHEDULE_WITH_ACCOUNT_ACCESS"
    else:
        verdict = "NO_STRUCTURAL_CONTRADICTION_VERIFY_SCHEDULE_WITH_ACCOUNT_ACCESS"

    out = {
        "hypothesis_id": "CRYPTO-007",
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "research/crypto/hypotheses/CRYPTO-007-prereg.json",
        "derived_from": "research/crypto/results/CRYPTO-006-probe.json",
        "new_market_data_downloaded": False,
        "oos_partition_read": False,
        "credentials_used": False,
        "band_median_90d_volume_usd": round(med_vol, 2),
        "symbols": dict(sorted(rows.items(),
                               key=lambda kv: -(kv[1]["f_be_lb95_bps"] or -99))),
        "fee_sweep_schedule_free": sweep,
        "gates": gates,
        "verdict": verdict,
        "interpretation": {
            "f_be_note": ("f_be is the maker fee at which the statistic turns positive. Because the "
                          "CRYPTO-006 reversal proxy OVERSTATES half-spread, every f_be here is an "
                          "UPPER bound: the true fee required is stricter than reported."),
            "schedule_note": ("No specific VIP tier table is load-bearing. Binance's published schedule "
                              "was not retrievable here (JS-gated pages; /fapi/v1/commissionRate is "
                              "signed USER_DATA and returns 401), and no credentials were used."),
            "monotonicity": "venue schedules are monotonically non-increasing maker fee in 30d volume",
        },
        "authority": {"live_capital": False, "paper_trading": False, "orders": False},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({"verdict": verdict, "gates": gates,
                      "fee_sweep": sweep}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
