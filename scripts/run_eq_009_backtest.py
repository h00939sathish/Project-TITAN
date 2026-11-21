"""High-Throughput Empirical Backtest Runner for EQ-009: Point-in-Time PEAD Factor Screen.

Loads:
- Dataset manifest: research/equities/manifests/us_sp50_earnings_pit_v1.json
- High-fidelity 5m intraday bars from research_data/intraday_5m/{sym}_5m.parquet (resampled to daily close)
- Causal point-in-time consensus earnings events: research/equities/data/us_sp50_earnings_events_v1.parquet
- Pre-registration specification: research/equities/hypotheses/EQ-009-prereg.json

Evaluates:
- All 7 canonical decision gates under baseline IBKR Pro fixed costs ($0.005/share, $1.00 min)
- Monotonicity across quintiles
- Stress adverse net return hurdle
- Seals the canonical evidence bundle at research/equities/results/EQ-009-evidence-bundle.json
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from titan.data.equities_universe import (
    EquitiesUniverseManifest,
    build_equities_universe,
)
from titan.research.equities_event_screen_009 import (
    load_factor_preregistration,
    load_pit_earnings_events,
    run_pit_screen_009,
)

CACHE_DIR = _REPO_ROOT / "research_data" / "intraday_5m"
MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_earnings_pit_v1.json"
EVENTS_PATH = _REPO_ROOT / "research" / "equities" / "data" / "us_sp50_earnings_events_v1.parquet"
PREREG_PATH = _REPO_ROOT / "research" / "equities" / "hypotheses" / "EQ-009-prereg.json"
RESULTS_PATH = _REPO_ROOT / "research" / "equities" / "results" / "EQ-009-evidence-bundle.json"


def verify_events_checksum(manifest: EquitiesUniverseManifest, events_path: Path) -> None:
    expected = manifest.checksums.get("us_sp50_earnings_events_v1.parquet")
    if not expected:
        return
    actual = hashlib.sha256(events_path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(
            f"Events file SHA-256 mismatch! Expected {expected}, got {actual}"
        )
    print(f"Verified events file SHA-256: {actual[:16]}... OK", flush=True)


def load_daily_prices(symbols: list[str]) -> dict[str, pd.Series]:
    print(f"Loading and resampling daily close prices for {len(symbols)} symbols...", flush=True)
    t0 = time.time()
    series_map: dict[str, pd.Series] = {}

    for sym in symbols:
        p = CACHE_DIR / f"{sym}_5m.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing price cache for symbol: {sym} at {p}")
        df = pd.read_parquet(p)
        ny_index = df.index.tz_convert("America/New_York")
        df["date"] = ny_index.date
        daily = df.groupby("date")["close"].last()
        daily.index = pd.to_datetime(daily.index)
        series_map[sym] = daily

    print(f"Loaded {len(symbols)} price series in {time.time() - t0:.2f}s.", flush=True)
    return series_map


def main() -> None:
    print("=" * 78, flush=True)
    print("PROJECT TITAN — EQ-009 Point-in-Time Consensus PEAD Backtest & Gate Evaluator", flush=True)
    print("=" * 78, flush=True)

    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    prereg = load_factor_preregistration(PREREG_PATH)
    verify_events_checksum(manifest, EVENTS_PATH)

    print(f"Dataset:       {manifest.dataset_name}", flush=True)
    print(f"Universe:      {len(manifest.universe)} liquid S&P large-cap equities", flush=True)
    print(f"IS Window:     {manifest.is_partition['from']} to {manifest.is_partition['to']}", flush=True)
    print(f"OOS Window:    {manifest.oos_partition['from']} to {manifest.oos_partition['to']}", flush=True)
    print(f"Strategy:      Top {prereg.parameters.get('top_k', 10)} Long / Bottom {prereg.parameters.get('bottom_k', 10)} Short (42-day drift)", flush=True)
    print(f"Fee Schedule:  IBKR Pro Fixed ($0.005/share, $1.00 min, 1.0 bps spread, 0.5 bps slippage)", flush=True)

    series_map = load_daily_prices(manifest.universe)
    universe = build_equities_universe(series_map, manifest)
    print(f"Aligned Matrix: {universe.prices.shape[0]} trading days x {universe.prices.shape[1]} equities", flush=True)

    events_df = load_pit_earnings_events(EVENTS_PATH)
    print(f"Loaded Events: {len(events_df):,} verified quarterly earnings releases", flush=True)

    print("\nRunning Point-in-Time PEAD Factor Screen & Evaluating Gates...", flush=True)
    t_start = time.time()
    bundle = run_pit_screen_009(universe, prereg, events_df, output_path=RESULTS_PATH)
    elapsed = time.time() - t_start
    print(f"Execution complete in {elapsed:.2f}s.", flush=True)

    gates_data = bundle["gates"]
    gates = gates_data["gates"]
    metrics = gates_data["metrics"]
    verdict = gates_data["verdict"]

    print("\n" + "=" * 78, flush=True)
    print(f"DECISION VERDICT: {verdict.upper()}", flush=True)
    print("=" * 78, flush=True)

    if "failure_mode" in gates_data:
        print(f"Failure Mode:   {gates_data['failure_mode'].upper()}", flush=True)
        print(f"Failure Basis:  {gates_data['failure_mode_basis']}", flush=True)

    print("\nGate Breakdown:", flush=True)
    for g_id, passed in gates.items():
        status = "PASSED [OK]" if passed else "FAILED [FAIL]"
        print(f"  {g_id:32s} : {status}", flush=True)

    print("\nEmpirical Metrics (OOS 2023-2024):", flush=True)
    print(f"  - Net Sharpe Ratio:            {metrics.get('net_sharpe', 0.0):.2f} (Hurdle >= {prereg.pass_criteria['min_oos_net_sharpe']:.2f})", flush=True)
    print(f"  - Annualized Net Return:       {metrics.get('annualized_net_return_pct', 0.0):.2f}%", flush=True)
    print(f"  - Rank IC Mean:                {metrics.get('mean_rank_ic', 0.0):.4f} (Hurdle >= {prereg.pass_criteria['min_mean_rank_ic']:.4f})", flush=True)
    print(f"  - IC Positive Fraction:        {metrics.get('ic_positive_fraction', 0.0):.1%} (Hurdle >= {prereg.pass_criteria['min_ic_positive_frac']:.1%})", flush=True)
    print(f"  - Maximum Drawdown:            {metrics.get('max_drawdown_pct', 0.0):.2f}% (Limit <= {prereg.pass_criteria['max_drawdown']*100:.1f}%)", flush=True)
    print(f"  - Monthly Turnover:            {metrics.get('monthly_turnover', 0.0):.1%} (Limit <= {prereg.pass_criteria['max_monthly_turnover']*100:.1f}%)", flush=True)
    print(f"  - Stressed Adverse Net Return: {metrics.get('adverse_net_return_pct', 0.0):.2f}% (Hurdle > {prereg.pass_criteria['min_adverse_net_return']*100:.1f}%)", flush=True)
    print(f"  - Friction Drag Ratio:         {metrics.get('friction_drag_ratio', 0.0):.1%}", flush=True)

    print("\nMonotonicity Profile:", flush=True)
    for q_name, q_val in bundle["monotonicity"].items():
        print(f"  {q_name:24s}: {q_val:+.2%}", flush=True)

    print(f"\nCanonical Evidence Bundle sealed to:\n  {RESULTS_PATH}", flush=True)
    print("=" * 78, flush=True)


if __name__ == "__main__":
    main()
