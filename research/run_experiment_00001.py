#!/usr/bin/env python3
"""Research Experiment EXP-00001 — Revised

Question: Does volatility contraction followed by strong relative strength
          predict positive 20-day returns?

Improvements over V1:
  - Cross-sectional relative strength (rank across universe)
  - Multi-instrument validation (SPY, QQQ, TLT)
  - Bootstrap confidence intervals
  - Temporal stability (3 periods)
  - Explicit research decision
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from titan.research.dataset import DatasetContract
from titan.research.feature import get_registry
from titan.research.features import (
    compute_atr_percentile,
    compute_forward_return,
    compute_return,
)
from titan.research.registrations import __name__ as _  # noqa: F401 — register features
from titan.research.experiment import Experiment
from titan.research.validator import (
    run_validators,
    cross_instrument_ic,
    make_decision,
)


def load_dataset(path: str, dataset_id: str, symbol: str) -> tuple[DatasetContract, list[dict]]:
    return DatasetContract.from_csv(path, id=dataset_id, symbol=symbol)


def run_single_instrument(
    rows: list[dict],
    benchmark_rows: list[dict] | None,
    experiment: Experiment,
    instrument_label: str,
) -> dict:
    """Run the experiment on one instrument and return evidence."""
    atr_pct = compute_atr_percentile(rows, 14, 252)
    rs_vals: list[float | None] | None = None

    if benchmark_rows:
        rs_vals = compute_return_vs_benchmark(rows, benchmark_rows, 60)
    else:
        from titan.research.features import compute_return
        rs_vals = compute_return(rows, 60)

    target_values = compute_forward_return(rows, 20)

    # Filter: volatility contraction (< 20th percentile ATR) + positive RS
    vol_contract_threshold = 0.20
    filtered_feature: list[float | None] = []
    filtered_target: list[float | None] = []

    for i in range(len(rows)):
        is_contracted = atr_pct[i] is not None and atr_pct[i] < vol_contract_threshold
        is_strong_rs = rs_vals[i] is not None and rs_vals[i] > 0
        if is_contracted and is_strong_rs and target_values[i] is not None:
            filtered_feature.append(rs_vals[i])
            filtered_target.append(target_values[i])
        else:
            filtered_feature.append(None)
            filtered_target.append(None)

    filter_hits = sum(1 for f in filtered_feature if f is not None)

    # Run validators
    evidence, checks, bootstrap_res, temporal_res = run_validators(
        filtered_feature, filtered_target,
        experiment_id=f"{experiment.id}/{instrument_label}",
        dataset_id=f"{experiment.dataset_id}/{instrument_label}",
    )

    return {
        "instrument": instrument_label,
        "rows": len(rows),
        "filter_hits": filter_hits,
        "evidence": evidence,
        "checks": checks,
        "bootstrap": bootstrap_res,
        "temporal": temporal_res,
    }


def compute_return_vs_benchmark(
    primary: list[dict],
    benchmark: list[dict],
    period: int = 60,
) -> list[float | None]:
    """Primary return minus benchmark return (relative strength)."""
    p_ret = compute_return(primary, period)
    b_ret = compute_return(benchmark, period)
    return [
        (p - b) if (p is not None and b is not None) else None
        for p, b in zip(p_ret, b_ret)
    ]


def compute_cross_sectional_relative_strength(
    datasets: dict[str, list[dict]],
    period: int = 60,
) -> dict[str, list[float | None]]:
    """For each date, rank each instrument by its period return.
    Returns percentile rank (0-1) for each instrument on each date.
    This is true cross-sectional relative strength.
    """
    # First compute raw returns for each instrument
    raw_returns: dict[str, list[float | None]] = {}
    for name, rows in datasets.items():
        raw_returns[name] = compute_return(rows, period)

    n = len(datasets)
    result: dict[str, list[float | None]] = {name: [] for name in datasets}

    for i in range(len(next(iter(datasets.values())))):
        # Get returns for all instruments at this timestamp
        period_rets: list[tuple[str, float]] = []
        for name, rows in datasets.items():
            r = raw_returns[name][i]
            if r is not None:
                period_rets.append((name, r))

        # Rank and assign percentile
        if len(period_rets) >= 2:
            sorted_rets = sorted(period_rets, key=lambda x: x[1])
            for rank_idx, (name, _) in enumerate(sorted_rets):
                percentile = rank_idx / (len(sorted_rets) - 1)  # 0 to 1
                result[name].append(percentile)
        else:
            for name in datasets:
                result[name].append(None)

    return result


def main():
    print("═══ TITAN Research — Experiment EXP-00001 (Revised) ═══")
    print()

    fixture_dir = Path(__file__).resolve().parents[1] / "tests/fixtures/market"

    # ── 1. Load all datasets ──────────────────────────────────────────
    instruments = {
        "SPY": fixture_dir / "spy_2020_2024.csv",
        "QQQ": fixture_dir / "qqq_2020_2024.csv",
        "TLT": fixture_dir / "tlt_2020_2024.csv",
    }

    datasets: dict[str, tuple[DatasetContract, list[dict]]] = {}
    all_rows: dict[str, list[dict]] = {}
    for name, path in instruments.items():
        contract, rows = load_dataset(str(path), f"{name.lower()}_daily_v1", name)
        datasets[name] = (contract, rows)
        all_rows[name] = rows
        print(f"📊 {name}: {contract.start} → {contract.end}  ({len(rows)} rows)")

    # Align all datasets to common dates
    common_dates: set[str] | None = None
    for name, rows in all_rows.items():
        dates = {r["date"] for r in rows}
        if common_dates is None:
            common_dates = dates
        else:
            common_dates &= dates

    common_dates_sorted = sorted(common_dates) if common_dates else []
    print(f"\n   Common trading days: {len(common_dates_sorted)}")
    print(f"   Range: {common_dates_sorted[0]} → {common_dates_sorted[-1]}")

    aligned: dict[str, list[dict]] = {}
    for name, rows in all_rows.items():
        date_map = {r["date"]: r for r in rows}
        aligned[name] = [date_map[d] for d in common_dates_sorted]

    # Replace all_rows with aligned version
    all_rows = aligned

    print()

    # ── 2. Define experiment ──────────────────────────────────────────
    experiment = Experiment(
        id="EXP-00001",
        question="Does volatility contraction followed by strong relative strength "
                 "predict positive 20-day returns?",
        dataset_id="multi_instrument_v1",
        features=("atr_percentile_20", "relative_strength_60d"),
        target="forward_return_20d",
    )
    print(f"🔬 {experiment.id}: {experiment.question}")
    print(f"   Features: {experiment.features}")
    print(f"   Universe: {list(instruments.keys())}")
    print()

    # ── 3. Compute cross-sectional relative strength (rank-based) ────────
    cs_rs = compute_cross_sectional_relative_strength(all_rows)

    # ── 4. Run experiment per instrument ──────────────────────────────
    results: dict[str, dict] = {}
    for name, rows in all_rows.items():
        atr_pct = compute_atr_percentile(rows, 14, 252)
        target = compute_forward_return(rows, 20)
        rs_pct = cs_rs[name]

        # Filter: volatility contraction + top-half RS (percentile > 0.5)
        vol_contract_threshold = 0.20
        filtered_f: list[float | None] = []
        filtered_t: list[float | None] = []
        for i in range(len(rows)):
            is_contracted = atr_pct[i] is not None and atr_pct[i] < vol_contract_threshold
            is_strong_rs = rs_pct[i] is not None and rs_pct[i] >= 0.5
            if is_contracted and is_strong_rs and target[i] is not None:
                filtered_f.append(rs_pct[i])
                filtered_t.append(target[i])
            else:
                filtered_f.append(None)
                filtered_t.append(None)

        filter_hits = sum(1 for f in filtered_f if f is not None)
        evidence, checks, boot, temporal = run_validators(
            filtered_f, filtered_t,
            experiment_id=f"{experiment.id}/{name}",
            dataset_id=f"{name.lower()}_daily_v1",
        )

        results[name] = {
            "rows": len(rows),
            "filter_hits": filter_hits,
            "pct_filtered": filter_hits / len(rows) * 100,
            "evidence": evidence,
            "checks": checks,
            "bootstrap": boot,
            "temporal": temporal,
        }

    # ── 5. Cross-instrument aggregation ──────────────────────────────
    cross_result = cross_instrument_ic({
        name: res["evidence"] for name, res in results.items()
    })

    # ── 6. Display results ────────────────────────────────────────────
    print("═══ Per-Instrument Results ═══")
    for name, res in results.items():
        e = res["evidence"]
        print(f"\n{name}:")
        print(f"  Filter hits: {res['filter_hits']}/{res['rows']} ({res['pct_filtered']:.1f}%)")
        print(f"  IC:          {e['ic']:.4f}  (p={e['p_value']:.4f})")
        print(f"  Bootstrap:   median={e['bootstrap']['median_ic']:.4f}  "
              f"CI=[{e['bootstrap']['ci_lower']:.4f}, {e['bootstrap']['ci_upper']:.4f}]")
        periods_str = ", ".join(f"period{p['period']}: {p['ic']:.3f}" for p in e["temporal"])
        print(f"  Temporal:    {periods_str}")
        for check, result in res["checks"].items():
            icon = "✅" if result is True else ("❌" if result is False else "⚠️")
            print(f"  {icon} {check}: {result}")

    # ── 7. Cross-instrument summary ──────────────────────────────────
    print(f"\n═══ Cross-Instrument Summary ═══")
    print(f"  Mean IC:      {cross_result['mean_ic']:.4f}")
    print(f"  IC range:     [{cross_result['min_ic']:.4f}, {cross_result['max_ic']:.4f}]")
    print(f"  Consistency:  {cross_result['sign_consistency']:.0%}")
    print(f"  Instruments:  {cross_result['instrument_count']}")
    for inst, ic in cross_result.get("per_instrument", {}).items():
        print(f"    {inst}: IC={ic:.4f}")

    # ── 8. Research Decision ──────────────────────────────────────────
    # Aggregate all checks across all instruments
    all_checks: dict[str, bool | str] = {}
    for name, res in results.items():
        for check, val in res["checks"].items():
            key = f"{name}: {check}"
            all_checks[key] = val

    bootstrap_medians = [res["evidence"]["bootstrap"]["median_ic"] for res in results.values()]
    bootstrap_ci_lowers = [res["evidence"]["bootstrap"]["ci_lower"] for res in results.values()]
    bootstrap_ci_uppers = [res["evidence"]["bootstrap"]["ci_upper"] for res in results.values()]

    all_ci_same_sign = all(
        lo > 0 or hi < 0
        for lo, hi in zip(bootstrap_ci_lowers, bootstrap_ci_uppers)
    )

    decision = make_decision(
        all_checks,
        {
            "ci_lower": min(bootstrap_ci_lowers),
            "ci_upper": max(bootstrap_ci_uppers),
        },
        results.get("SPY", {}).get("temporal", []),
        cross_instrument=cross_result,
    )

    print(f"\n═══ Decision ═══")
    print(decision.summary())
    print()

    # ── 9. Save ──────────────────────────────────────────────────────
    results_dir = Path("research/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    result_file = results_dir / f"{experiment.id}_v2.json"
    output = {
        "experiment": {
            "id": experiment.id,
            "question": experiment.question,
            "features": list(experiment.features),
            "target": experiment.target,
        },
        "per_instrument": {
            name: {
                "filter_hits": res["filter_hits"],
                "total_rows": res["rows"],
                "ic": round(res["evidence"]["ic"], 4),
                "p_value": round(res["evidence"]["p_value"], 4),
                "sample_size": res["evidence"]["sample_size"],
                "bootstrap": res["bootstrap"],
                "temporal": res["temporal"],
                "checks": {k: str(v) if not isinstance(v, bool) else v
                          for k, v in res["checks"].items()},
            }
            for name, res in results.items()
        },
        "cross_instrument": cross_result,
        "decision": {
            "status": decision.status,
            "confidence": decision.confidence,
            "reasons": decision.reasons,
        },
    }
    with open(result_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"📁 Results saved to {result_file}")


if __name__ == "__main__":
    main()
