#!/usr/bin/env python3
"""EXP-00021 — daily-scale time-series momentum (the literature's strongest FX
family, MOP 2012) on 8 years of EURUSD/GBPUSD daily bars.

Signal: trailing N-day return (N in {21, 63, 126, 252}). Target: forward M-day
return (M in {21, 63}). TSM predicts POSITIVE autocorrelation (expected_sign=+1).

Data: research/tws_daily/*.json (Yahoo CCY, 2018-07 -> 2026-07, 2,084 bars/pair).
Run:  python research/run_exp21_tsm_daily.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from titan.research.experiment import Experiment
from titan.research.validator import (
    run_validators,
    cross_instrument_ic,
    make_decision,
)

DATA = Path(__file__).resolve().parents[1] / "research" / "tws_daily"
LOOKBACKS = (21, 63, 126, 252)
HORIZONS = (21, 63)


def load(sym: str) -> list[dict]:
    return json.loads((DATA / f"{sym}.json").read_text(encoding="utf-8"))


def rolling_return(closes, period):
    return [closes[i] / closes[i - period] - 1.0 if i >= period else None
            for i in range(len(closes))]


def forward_return(closes, horizon):
    return [closes[i + horizon] / closes[i] - 1.0 if i + horizon < len(closes) else None
            for i in range(len(closes))]


def main():
    print("═══ EXP-00021 — daily time-series momentum (MOP 2012 replication) ═══")
    rows = {s: load(s) for s in ("EURUSD", "GBPUSD")}
    closes = {s: [float(b["close"]) for b in rows[s]] for s in rows}
    for s in rows:
        print(f"📊 {s}: {len(rows[s])} daily bars "
              f"({rows[s][0]['timestamp'][:10]} -> {rows[s][-1]['timestamp'][:10]})")

    print(f"\n{'lookback':>9}{'horizon':>9}{'EUR IC':>10}{'GBP IC':>10}{'mean':>8}"
          f"{'consist':>9}{'n':>7}  decision")
    print("-" * 78)
    combos = [(lb, hz) for lb in LOOKBACKS for hz in HORIZONS]
    results = {}
    for lb, hz in combos:
        fvals, tvals = {}, {}
        for s in closes:
            fvals[s] = rolling_return(closes[s], lb)
            tvals[s] = forward_return(closes[s], hz)
        ic_s = {}
        checks_all = {}
        boot_lows, boot_highs, temporals = [], [], []
        for s in closes:
            evidence, checks, _, temporal = run_validators(
                fvals[s], tvals[s],
                experiment_id=f"EXP-00021/{s}",
                dataset_id=f"tws_daily_v1/{s}",
                cost_bps=10.0,
                n_bootstrap=300,
            )
            ic_s[s] = evidence["ic"]
            boot_lows.append(evidence["bootstrap"]["ci_lower"])
            boot_highs.append(evidence["bootstrap"]["ci_upper"])
            temporals.append(temporal)
            for k, v in checks.items():
                checks_all[f"{s}: {k}"] = v
        cross = cross_instrument_ic({s: {"ic": v, "sample_size": len(rows[s])} for s, v in ic_s.items()})
        decision = make_decision(
            checks_all,
            {"ci_lower": min(boot_lows), "ci_upper": max(boot_highs)},
            temporals[0],
            cross_instrument=cross,
            experiment_index=combos.index((lb, hz)),
            total_experiments=len(combos),
            expected_sign=+1,
        )
        mean_ic = (ic_s["EURUSD"] + ic_s["GBPUSD"]) / 2
        n = len(rows["EURUSD"]) - lb - hz
        print(f"{lb:>9}{hz:>9}{ic_s['EURUSD']:>10.4f}{ic_s['GBPUSD']:>10.4f}{mean_ic:>8.4f}"
              f"{cross['sign_consistency']:>7.0%}{n:>7}  {decision.status}")
        results[(lb, hz)] = {"ic": ic_s, "decision": decision.status}

    print("\nVerdict: TSM predicts POSITIVE autocorrelation (continuation). Positive")
    print("ICs with 100% consistency = the literature effect replicates in our window.")


if __name__ == "__main__":
    main()
