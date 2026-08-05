"""Run full qualification matrix across Equities and Forex datasets and timeframes."""

import json
import sys
from pathlib import Path

from titan.strategies.registry import get_registry
import titan.strategies.registrations  # noqa: F401
from qualification_pipeline import qualify_strategy, QUALIFICATION_CRITERIA, load_bars, Status

ROOT_DIR = Path(__file__).resolve().parent.parent
INTRADAY_DIR = ROOT_DIR / "research" / "intraday_backtests" / "2026-07-29"
DAILY_CSV = ROOT_DIR / "tests" / "fixtures" / "market" / "real_spy_2020_2024.csv"
OUT_DIR = ROOT_DIR / "scripts" / "qualification_output"


DATASETS = [
    {
        "symbol": "SPY",
        "timeframe": "1d",
        "asset_class": "equity",
        "path": DAILY_CSV,
        "is_unapproved": False,
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    {
        "symbol": "SPY",
        "timeframe": "1h",
        "asset_class": "equity",
        "path": INTRADAY_DIR / "spy_1h.csv",
        "is_unapproved": False,
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    {
        "symbol": "SPY",
        "timeframe": "15m",
        "asset_class": "equity",
        "path": INTRADAY_DIR / "spy_15m.csv",
        "is_unapproved": False,
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    {
        "symbol": "SPY",
        "timeframe": "5m",
        "asset_class": "equity",
        "path": INTRADAY_DIR / "spy_5m.csv",
        "is_unapproved": False,
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "asset_class": "forex",
        "path": INTRADAY_DIR / "eurusd_1h.csv",
        "is_unapproved": True,  # yfinance source
        "slippage_bps": 1.0,
        "commission_bps": 1.0,
    },
    {
        "symbol": "EURUSD",
        "timeframe": "15m",
        "asset_class": "forex",
        "path": INTRADAY_DIR / "eurusd_15m.csv",
        "is_unapproved": True,  # yfinance source
        "slippage_bps": 1.0,
        "commission_bps": 1.0,
    },
    {
        "symbol": "EURUSD",
        "timeframe": "5m",
        "asset_class": "forex",
        "path": INTRADAY_DIR / "eurusd_5m.csv",
        "is_unapproved": True,  # yfinance source
        "slippage_bps": 1.0,
        "commission_bps": 1.0,
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strategy_ids = get_registry().list_ids()
    matrix_results = []

    print("==========================================================================")
    print("  TITAN Multi-Asset Multi-Timeframe Strategy Qualification Matrix")
    print("==========================================================================")

    for dataset in DATASETS:
        csv_path = dataset["path"]
        if not csv_path.exists():
            print(f"Skipping missing dataset: {csv_path}")
            continue

        print(f"\n--- Processing {dataset['symbol']} [{dataset['timeframe']}] ({dataset['asset_class'].upper()}) ---")
        try:
            bars = load_bars(str(csv_path))
        except Exception as e:
            print(f"Error loading {csv_path}: {e}")
            continue

        print(f"  Loaded {len(bars)} bars from {csv_path.name}")

        for sid in strategy_ids:
            q = qualify_strategy(
                bars,
                sid,
                slippage_bps=dataset["slippage_bps"],
                commission_bps=dataset["commission_bps"],
                is_unapproved_source=dataset["is_unapproved"],
            )
            if q:
                res = {
                    "symbol": dataset["symbol"],
                    "timeframe": dataset["timeframe"],
                    "asset_class": dataset["asset_class"],
                    "strategy_id": sid,
                    "best_params": q.best_params,
                    "is_sharpe": q.is_sharpe,
                    "oos_sharpe": q.oos_sharpe,
                    "wf_mean_sharpe": q.wf_mean_sharpe,
                    "total_return_pct": q.total_return_pct,
                    "max_dd_pct": q.max_dd_pct,
                    "total_trades": q.total_trades,
                    "status": q.status,
                    "confidence": q.confidence,
                    "reasons": q.reasons,
                }
                matrix_results.append(res)
                print(f"    {sid:22s} [{dataset['timeframe']:4s}] IS Sharpe={q.is_sharpe:5.2f} | OOS Sharpe={q.oos_sharpe:5.2f} | Status={q.status}")

    # Write JSON summary
    matrix_file = OUT_DIR / "full_qualification_matrix.json"
    matrix_file.write_text(json.dumps(matrix_results, indent=2), encoding="utf-8")

    # Print summary table
    print("\n" + "=" * 100)
    print("  QUALIFICATION MATRIX SUMMARY")
    print("=" * 100)
    print(f"{'Symbol':7s} | {'TF':4s} | {'Strategy':22s} | {'IS Sharpe':9s} | {'OOS Sharpe':10s} | {'Return%':8s} | {'Status':10s}")
    print("-" * 100)
    for r in matrix_results:
        print(f"{r['symbol']:7s} | {r['timeframe']:4s} | {r['strategy_id']:22s} | {r['is_sharpe']:9.2f} | {r['oos_sharpe']:10.2f} | {r['total_return_pct']:7.1f}% | {r['status']:10s}")
    print("=" * 100)
    print(f"\nSaved full matrix to {matrix_file}\n")


if __name__ == "__main__":
    main()
