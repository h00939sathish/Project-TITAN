"""High-Throughput Batch Historical Data Ingestion & Evaluator for EQ-Micro-001.

Batches requests across 54 instruments (4 ETFs + 50 Equities) in 10-asset chunks,
streams 5-minute bars over 2020-2024 from Alpaca, caches to research_data/intraday_5m/,
builds point-in-time universe, evaluates the 7 decision gates, and writes evidence bundle.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
load_dotenv(dotenv_path=_REPO_ROOT / ".env")

from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from titan.data.alpaca_feed import AlpacaDataFeed
from titan.data.equities_intraday import (
    EquitiesIntradayManifest,
    build_intraday_universe,
)
from titan.research.equities_micro_screen_001 import (
    load_factor_preregistration,
    run_micro_screen_001,
)

CACHE_DIR = _REPO_ROOT / "research_data" / "intraday_5m"
MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_liquid_intraday_v1.json"
PREREG_PATH = _REPO_ROOT / "research" / "equities" / "hypotheses" / "EQ-Micro-001-prereg.json"
RESULTS_PATH = _REPO_ROOT / "research" / "equities" / "results" / "EQ-Micro-001-evidence-bundle.json"


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


def ingest_all_intraday(feed: AlpacaDataFeed, symbols: list[str]) -> dict[str, pd.Series]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    series_map: dict[str, pd.Series] = {}

    missing_symbols = []
    for s in symbols:
        cache_path = CACHE_DIR / f"{s}_5m.parquet"
        if cache_path.exists():
            df = pd.read_parquet(cache_path)
            series_map[s] = df["close"]
        else:
            missing_symbols.append(s)

    if not missing_symbols:
        print(f"All {len(symbols)} symbols loaded directly from local parquet cache.", flush=True)
        return series_map

    print(f"Ingesting {len(missing_symbols)} symbols across 2020-2024 via Alpaca batch streams...", flush=True)

    years = [2020, 2021, 2022, 2023, 2024]
    symbol_chunks = list(chunked(missing_symbols, 10))

    # Ingest year by year, chunk by chunk
    symbol_data: dict[str, list[dict]] = {s: [] for s in missing_symbols}

    for year in years:
        start_dt = datetime(year, 1, 1, 0, 0)
        end_dt = datetime(year, 12, 31, 23, 59)
        t_year_start = time.time()
        print(f"\n--- Ingesting Year {year} ({start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}) ---", flush=True)

        for c_idx, chunk in enumerate(symbol_chunks, 1):
            t0 = time.time()
            req = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                start=start_dt,
                end=end_dt,
                adjustment="all",
            )
            bar_set = feed._client.get_stock_bars(req)
            total_bars_chunk = 0
            for sym in chunk:
                raw = bar_set.data.get(sym, [])
                total_bars_chunk += len(raw)
                for b in raw:
                    symbol_data[sym].append({
                        "timestamp": pd.to_datetime(b.timestamp),
                        "close": float(b.close),
                        "volume": float(b.volume),
                    })
            elapsed = time.time() - t0
            print(f"  [Chunk {c_idx}/{len(symbol_chunks)}] Symbols {chunk} -> {total_bars_chunk:,} bars in {elapsed:.1f}s", flush=True)

        print(f"--- Year {year} complete in {time.time() - t_year_start:.1f}s ---", flush=True)

    # Cache each ingested symbol to disk
    print("\nSaving symbol parquets to disk cache...", flush=True)
    for sym in missing_symbols:
        recs = symbol_data[sym]
        if not recs:
            raise ValueError(f"No records retrieved for symbol {sym}")
        df = pd.DataFrame(recs).drop_duplicates(subset=["timestamp"]).set_index("timestamp").sort_index()
        cache_path = CACHE_DIR / f"{sym}_5m.parquet"
        df.to_parquet(cache_path)
        series_map[sym] = df["close"]
        print(f"  Cached {sym}: {len(df):,} bars -> {cache_path.name}", flush=True)

    return series_map


def main():
    print("=" * 70, flush=True)
    print("PROJECT TITAN — EQ-Micro-001 High-Throughput Batch Factor Screen", flush=True)
    print("=" * 70, flush=True)

    feed = AlpacaDataFeed(paper=True)
    manifest = EquitiesIntradayManifest.load(MANIFEST_PATH)
    prereg = load_factor_preregistration(PREREG_PATH)

    all_symbols = list(manifest.etf_anchors) + list(manifest.universe)
    print(f"Universe: {len(manifest.etf_anchors)} ETF anchors + {len(manifest.universe)} Equities = {len(all_symbols)} total instruments.", flush=True)
    print(f"Partitions: IS ({manifest.is_partition['from']} to {manifest.is_partition['to']}) | OOS ({manifest.oos_partition['from']} to {manifest.oos_partition['to']})", flush=True)

    series_map = ingest_all_intraday(feed, all_symbols)

    print("\nAligning intraday price matrix across all 54 instruments...", flush=True)
    univ = build_intraday_universe(series_map, manifest)
    print(f"Aligned Intraday Universe: {univ.prices.shape[0]:,} bars x {univ.prices.shape[1]} instruments.", flush=True)

    print("\nExecuting Factor Screen Pipeline & Gate Evaluation...", flush=True)
    t_eval = time.time()
    bundle = run_micro_screen_001(univ, prereg, output_path=RESULTS_PATH)
    print(f"Evaluation complete in {time.time() - t_eval:.1f}s.", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("EQ-Micro-001 EVALUATION RESULTS & DECISION GATES", flush=True)
    print("=" * 70, flush=True)

    gates = bundle["gates"]["gates"]
    metrics = bundle["gates"]["metrics"]
    verdict = bundle["gates"]["verdict"]

    print(f"VERDICT: {verdict.upper()}", flush=True)
    if "failure_mode" in bundle["gates"]:
        print(f"FAILURE MODE: {bundle['gates']['failure_mode']}", flush=True)
        print(f"FAILURE BASIS: {bundle['gates']['failure_mode_basis']}", flush=True)

    print("\nDecision Gate Breakdown:", flush=True)
    for gate_name, passed in gates.items():
        status = "PASSED [OK]" if passed else "FAILED [REJECT]"
        print(f"  - {gate_name:40s}: {status}", flush=True)

    print("\nPerformance & Risk Attribution:", flush=True)
    print(f"  - In-Sample (2020-2022) Net Sharpe:      {bundle['is']['annualized_net_sharpe']:.2f}", flush=True)
    print(f"  - Out-of-Sample (2023-2024) Net Sharpe:  {metrics['net_sharpe']:.2f} (Hurdle >= 1.20)", flush=True)
    print(f"  - OOS Annualized Net Return:            {metrics['annualized_net_return_pct']:.2f}%", flush=True)
    print(f"  - OOS Max Drawdown:                     {metrics['max_drawdown_pct']:.2f}% (Limit <= 6.0%)", flush=True)
    print(f"  - Mean Rank IC:                         {metrics['mean_rank_ic']:.4f} (Hurdle >= 0.03)", flush=True)
    print(f"  - Rank IC Positive Fraction:            {metrics['ic_positive_fraction']:.1%} (Hurdle >= 65.0%)", flush=True)
    print(f"  - Friction Drag Ratio:                  {metrics['friction_drag_ratio']:.1%} (Limit <= 45.0%)", flush=True)
    print(f"  - Stressed Adverse Net Return:          {metrics['adverse_net_return_pct']:.2f}% (Hurdle > 0.0%)", flush=True)
    print(f"\nCanonical Evidence Bundle sealed at: {RESULTS_PATH}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
