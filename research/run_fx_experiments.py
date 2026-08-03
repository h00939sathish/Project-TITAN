#!/usr/bin/env python3
"""FX experiments EXP-00016..EXP-00018 on tws_5m_v1 (real TWS midpoint data).

FX-001 (EXP-00016) Trend:  does trailing 12h return predict next 1h return?
FX-002 (EXP-00017) Vol:    does realized vol (20 bars) predict forward 1h |ret|?
FX-003 (EXP-00018) Calendar: does the London/NY overlap (12-16 UTC) differ in
                           forward 1h return / |return| vs the rest of the day?

All results are filed (research/results + research/experiments bundles).
Midpoint data: cost_bps=10 (~1 pip retail round trip) applied via the
validator's cost sensitivity gate.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from titan.research.dataset import DatasetContract
from titan.research.experiment import Experiment
from titan.research.validator import (
    run_validators,
    cross_instrument_ic,
    make_decision,
)

HISTORY = Path(__file__).resolve().parents[1] / "research" / "tws_history"
RESULTS = Path(__file__).resolve().parents[1] / "research" / "results"
BUNDLES = Path(__file__).resolve().parents[1] / "research" / "experiments"


def load_pair(symbol: str) -> tuple[DatasetContract, list[dict]]:
    bars = json.loads((HISTORY / f"{symbol}.json").read_text(encoding="utf-8"))
    rows = [{**b, "date": b["timestamp"]} for b in bars]
    contract = DatasetContract(
        id="tws_5m_v1",
        symbol=symbol,
        frequency="5min",
        adjusted=False,
        timezone="UTC",
        source="TWS",
        start=rows[0]["date"][:10],
        end=rows[-1]["date"][:10],
        description="IBKR TWS 5-min bars, MIDPOINT for CASH (see data_contracts.md)",
    )
    return contract, rows


def rolling_return(rows, period: int) -> list[float | None]:
    closes = [float(r["close"]) for r in rows]
    out = []
    for i in range(len(closes)):
        out.append(closes[i] / closes[i - period] - 1.0 if i >= period else None)
    return out


def forward_return(rows, horizon: int) -> list[float | None]:
    closes = [float(r["close"]) for r in rows]
    out = []
    for i in range(len(closes)):
        out.append(closes[i + horizon] / closes[i] - 1.0 if i + horizon < len(closes) else None)
    return out


def bar_log_returns(rows) -> list[float]:
    closes = [float(r["close"]) for r in rows]
    return [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]


def realized_vol(rows, period: int) -> list[float | None]:
    lr = bar_log_returns(rows)
    out: list[float | None] = [None]
    for i in range(1, len(rows)):
        if i < period:
            out.append(None)
        else:
            out.append(statistics.stdev(lr[i - period:i]))
    return out


def forward_abs_return(rows, horizon: int) -> list[float | None]:
    fwd = forward_return(rows, horizon)
    return [abs(f) if f is not None else None for f in fwd]


def session_overlap(rows) -> list[float | None]:
    """1.0 for bars with timestamp hour in 12..15 UTC (London/NY overlap)."""
    return [1.0 if int(r["date"][11:13]) in (12, 13, 14, 15) else 0.0 for r in rows]


def run_experiment(experiment: Experiment, feature_vals, target_vals, instruments,
                   expected_sign: int = 0) -> dict:
    print(f"\n🔬 {experiment.id}: {experiment.question}")
    results = {}
    for name, rows in instruments.items():
        idx = {sym: i for i, sym in enumerate(instruments)}
        _ = idx  # features are computed per-instrument before calling
        evidence, checks, boot, temporal = run_validators(
            feature_vals[name], target_vals[name],
            experiment_id=f"{experiment.id}/{name}",
            dataset_id=f"tws_5m_v1/{name}",
            cost_bps=10.0,
            n_bootstrap=300,
        )
        results[name] = {"rows": len(rows), "evidence": evidence, "checks": checks,
                         "bootstrap": boot, "temporal": temporal}
        e = evidence
        print(f"  {name}: IC={e['ic']:.4f} (p={e['p_value']:.4f}, n={e['sample_size']}) "
              f"boot=[{e['bootstrap']['ci_lower']:.4f},{e['bootstrap']['ci_upper']:.4f}]")
    cross = cross_instrument_ic({n: r["evidence"] for n, r in results.items()})
    print(f"  Cross: mean_ic={cross['mean_ic']:.4f} consistency={cross['sign_consistency']:.0%}")

    all_checks = {}
    for name, res in results.items():
        for check, val in res["checks"].items():
            all_checks[f"{name}: {check}"] = val
    decision = make_decision(
        all_checks,
        {"ci_lower": min(r["evidence"]["bootstrap"]["ci_lower"] for r in results.values()),
         "ci_upper": max(r["evidence"]["bootstrap"]["ci_upper"] for r in results.values())},
        list(results.values())[0]["temporal"],
        cross_instrument=cross,
        experiment_index=int(experiment.id.split("-")[1]) - 16,
        total_experiments=3,
        expected_sign=expected_sign,
    )
    print(f"  Decision: {decision.summary()}")
    return {"experiment": experiment, "results": results, "cross": cross, "decision": decision}


def save_bundle(exp: Experiment, run: dict, mechanism: str) -> None:
    BUNDLES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    bundle = {
        "experiment_id": exp.id,
        "canonical_research_question": exp.question,
        "hypothesis": exp.features,
        "economic_mechanism": mechanism,
        "instruments": list(run["results"].keys()),
        "governance_checks": {k: str(v) for k, v in
                              {ck: v for res in run["results"].values() for ck, v in res["checks"].items()}.items()},
        "decision": run["decision"].status,
        "results": {n: {"ic": round(r["evidence"]["ic"], 4), "n": r["evidence"]["sample_size"],
                        "bootstrap_ci": [round(r["evidence"]["bootstrap"]["ci_lower"], 4),
                                         round(r["evidence"]["bootstrap"]["ci_upper"], 4)],
                        "temporal": r["temporal"]} for n, r in run["results"].items()},
        "execution_timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    (BUNDLES / f"{exp.id}_evidence_bundle.json").write_text(json.dumps(bundle, indent=1), encoding="utf-8")
    (RESULTS / f"{exp.id}.json").write_text(json.dumps(bundle["results"], indent=1), encoding="utf-8")
    print(f"  saved: {exp.id} bundle + results")


def main():
    print("═══ TITAN Research — FX experiments EXP-00016..00018 (tws_5m_v1) ═══\n")
    pairs = {sym: load_pair(sym) for sym in ("EURUSD", "GBPUSD")}
    rows_by = {sym: rows for sym, (_, rows) in pairs.items()}
    for sym, (contract, rows) in pairs.items():
        print(f"📊 {sym}: {contract.start} → {contract.end} ({len(rows)} bars) source={contract.source}")

    # ── FX-001 (EXP-00016): intraday trend ─────────────────────────────
    exp16 = Experiment(
        id="EXP-00016",
        question="Does the trailing 12h EURUSD/GBPUSD return predict the next 1h return "
                 "(intraday analog of time-series momentum)?",
        economic_rationale="Time-series momentum is the most robust documented FX effect "
                           "(MOP 2012, monthly scale). This tests whether a 12h/1h intraday "
                           "analog carries any signal after ~1 pip round-trip costs.",
        dataset_id="tws_5m_v1",
        features=("return_12h",),
        target="forward_return_1h",
        params={"lookback_bars": 144, "forward_bars": 12},
    )
    f16 = {s: rolling_return(rows_by[s], 144) for s in rows_by}
    t16 = {s: forward_return(rows_by[s], 12) for s in rows_by}
    r16 = run_experiment(exp16, f16, t16, rows_by, expected_sign=+1)
    save_bundle(exp16, r16, "Positive autocorrelation in FX returns (documented at monthly horizon; intraday scale is exploratory)")

    # ── FX-002 (EXP-00017): volatility clustering ──────────────────────
    exp17 = Experiment(
        id="EXP-00017",
        question="Does realized volatility over the last ~1.7h (20 bars) predict the "
                 "magnitude of the next 1h move?",
        economic_rationale="Volatility clustering is among the most robust facts in FX "
                           "(Andersen-Bollerslev 1998). If it holds intraday, it powers the "
                           "vol-scaling risk layer (Moreira-Muir 2017).",
        dataset_id="tws_5m_v1",
        features=("realized_vol_20",),
        target="forward_abs_return_1h",
        params={"vol_period_bars": 20, "forward_bars": 12},
    )
    f17 = {s: realized_vol(rows_by[s], 20) for s in rows_by}
    t17 = {s: forward_abs_return(rows_by[s], 12) for s in rows_by}
    r17 = run_experiment(exp17, f17, t17, rows_by, expected_sign=+1)
    save_bundle(exp17, r17, "Volatility clustering / ARCH effects in FX returns")

    # ── FX-003 (EXP-00018): London/NY session calendar effect ──────────
    exp18 = Experiment(
        id="EXP-00018",
        question="Does the London/NY overlap (12-16 UTC) have a different forward 1h "
                 "return profile than the rest of the day?",
        economic_rationale="FX liquidity and volatility concentrate in the London/NY "
                           "overlap (Andersen-Bollerslev 1998). The session flag tests "
                           "whether scheduling trades there changes expected return/risk.",
        dataset_id="tws_5m_v1",
        features=("session_overlap_12_16utc",),
        target="forward_return_1h",
        params={"overlap_hours": (12, 13, 14, 15)},
    )
    f18 = {s: session_overlap(rows_by[s]) for s in rows_by}
    t18 = {s: forward_return(rows_by[s], 12) for s in rows_by}
    r18 = run_experiment(exp18, f18, t18, rows_by)
    save_bundle(exp18, r18, "Intraday seasonality of FX returns (calendar effect)")

    # Supplementary: overlap vs |return| (vol by session)
    print("\n  (supplementary) mean |1h move| inside vs outside overlap:")
    for s in rows_by:
        rows = rows_by[s]
        ov = session_overlap(rows)
        av = forward_abs_return(rows, 12)
        inside = [a for o, a in zip(ov, av) if o == 1.0 and a is not None]
        outside = [a for o, a in zip(ov, av) if o == 0.0 and a is not None]
        print(f"    {s}: inside={sum(inside)/len(inside)*10000:.2f} pips  outside={sum(outside)/len(outside)*10000:.2f} pips")

    # ── FX-004 (EXP-00019): intraday reversal (falsified momentum, flipped) ─
    exp19 = Experiment(
        id="EXP-00019",
        question="Does the intraday reversal signal (negative of the trailing 12h "
                 "return) predict the next 1h return — and does it survive ~1 pip "
                 "round-trip costs?",
        economic_rationale="EXP-00016 falsified intraday momentum with a strongly "
                           "negative IC; the evidence supported the OPPOSITE direction. "
                           "This tests the reversal hypothesis directly, with an "
                           "economic-magnitude check (quintile spread in pips) in "
                           "addition to IC.",
        dataset_id="tws_5m_v1",
        features=("reversal_signal_12h",),
        target="forward_return_1h",
        params={"lookback_bars": 144, "forward_bars": 12, "cost_pips_rt": 1.0},
    )
    f19 = {s: [-r if r is not None else None for r in rolling_return(rows_by[s], 144)] for s in rows_by}
    t19 = {s: forward_return(rows_by[s], 12) for s in rows_by}
    r19 = run_experiment(exp19, f19, t19, rows_by, expected_sign=+1)
    save_bundle(exp19, r19, "Intraday mean reversion: short-horizon reversal after 12h moves")

    print("\n  (economic magnitude) next-1h move by reversal-signal quintile, in pips:")
    for s in rows_by:
        rows = rows_by[s]
        f, t = f19[s], t19[s]
        pairs = [(fv, tv) for fv, tv in zip(f, t) if fv is not None and tv is not None]
        pairs.sort(key=lambda p: p[0])
        n = len(pairs)
        qsize = n // 5
        q_means = []
        for q in range(5):
            chunk = pairs[q * qsize:(q + 1) * qsize]
            mean_pips = sum(p[1] for p in chunk) / len(chunk) * 10000
            q_means.append(mean_pips)
        top, bot = q_means[4], q_means[0]
        spread = top - bot
        # overlap-only (12-16 UTC) version
        ov = session_overlap(rows)
        pairs_ov = [(fv, tv) for fv, tv, o in zip(f, t, ov) if fv is not None and tv is not None and o == 1.0]
        pairs_ov.sort(key=lambda p: p[0])
        n_ov = len(pairs_ov)
        q_ov = n_ov // 5
        top_ov = sum(p[1] for p in pairs_ov[4 * q_ov:5 * q_ov]) / q_ov * 10000 if q_ov else 0.0
        bot_ov = sum(p[1] for p in pairs_ov[0:q_ov]) / q_ov * 10000 if q_ov else 0.0
        print(f"    {s}: quintile means={['%.2f' % m for m in q_means]} pips | "
              f"top-bottom={spread:.2f} pips (net of 1.0 pip RT: {spread - 1.0:.2f}) | "
              f"overlap-only top-bottom={top_ov - bot_ov:.2f} pips")

    print("\n═══ Done. Bundles in research/experiments, results in research/results ═══")


if __name__ == "__main__":
    main()
