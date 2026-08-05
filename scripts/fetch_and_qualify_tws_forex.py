"""Fetch official TWS historical Forex & Equity bars and run qualification pipeline."""

import csv
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from titan.data.tws_feed import TWSDataFeed
from qualification_pipeline import qualify_strategy, load_bars, Status
from titan.strategies.registrations import get_registry

OUT_DIR = ROOT_DIR / "research" / "intraday_backtests" / "tws_approved"


TASKS = [
    {"symbol": "EURUSD", "timeframe": "1h", "bar_size": "1 hour", "duration": "1 M", "asset_class": "forex", "file": "eurusd_1h_tws.csv"},
    {"symbol": "EURUSD", "timeframe": "15m", "bar_size": "15 mins", "duration": "1 W", "asset_class": "forex", "file": "eurusd_15m_tws.csv"},
    {"symbol": "EURUSD", "timeframe": "5m", "bar_size": "5 mins", "duration": "3 D", "asset_class": "forex", "file": "eurusd_5m_tws.csv"},
    {"symbol": "SPY", "timeframe": "1h", "bar_size": "1 hour", "duration": "1 M", "asset_class": "equity", "file": "spy_1h_tws.csv"},
]


def save_to_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not bars:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for b in bars:
            writer.writerow({
                "timestamp": b.get("timestamp", ""),
                "open": b.get("open", b.get("close")),
                "high": b.get("high", b.get("close")),
                "low": b.get("low", b.get("close")),
                "close": b.get("close"),
                "volume": b.get("volume", 0),
            })


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("==========================================================================")
    print("  Fetching Official TWS Broker Bars & Running Qualification")
    print("==========================================================================")

    try:
        feed = TWSDataFeed(port=7497)
        print("Connected to TWS on port 7497.")
    except Exception as e:
        print(f"Failed to connect to TWS on port 7497: {e}")
        sys.exit(1)

    tws_results = []
    strategy_ids = get_registry().list_ids()

    for t in TASKS:
        print(f"\n--- Fetching TWS Historical Data for {t['symbol']} [{t['timeframe']}] ({t['bar_size']}) ---")
        bars = feed.fetch_to_approved(t["symbol"], bar_size=t["bar_size"], duration=t["duration"])
        csv_path = OUT_DIR / t["file"]

        if not bars:
            print(f"  Warning: No bars returned from TWS for {t['symbol']} [{t['timeframe']}]")
            continue

        print(f"  Fetched {len(bars)} official TWS bars ({bars[0]['timestamp']} to {bars[-1]['timestamp']})")
        save_to_csv(bars, csv_path)

        # Run qualification using official broker data (is_unapproved_source = False)
        slippage = 1.0 if t["asset_class"] == "forex" else 0.5
        commission = 1.0 if t["asset_class"] == "forex" else 1.0

        for sid in strategy_ids:
            q = qualify_strategy(
                bars,
                sid,
                slippage_bps=slippage,
                commission_bps=commission,
                is_unapproved_source=False,  # Official TWS broker feed!
            )
            if q:
                res = {
                    "symbol": t["symbol"],
                    "timeframe": t["timeframe"],
                    "asset_class": t["asset_class"],
                    "strategy_id": sid,
                    "best_params": q.best_params,
                    "is_sharpe": q.is_sharpe,
                    "oos_sharpe": q.oos_sharpe,
                    "wf_mean_sharpe": q.wf_mean_sharpe,
                    "total_return_pct": q.total_return_pct,
                    "status": q.status,
                    "confidence": q.confidence,
                    "reasons": q.reasons,
                }
                tws_results.append(res)
                print(f"    {sid:22s} [{t['timeframe']:4s}] IS Sharpe={q.is_sharpe:5.2f} | OOS Sharpe={q.oos_sharpe:5.2f} | Status={q.status}")

    feed.disconnect()

    # Output summary
    report_file = OUT_DIR / "tws_qualification_report.json"
    report_file.write_text(json.dumps(tws_results, indent=2), encoding="utf-8")

    print("\n" + "=" * 90)
    print("  OFFICIAL TWS QUALIFICATION RESULTS")
    print("=" * 90)
    print(f"{'Symbol':7s} | {'TF':4s} | {'Strategy':22s} | {'IS Sharpe':9s} | {'OOS Sharpe':10s} | {'Status':10s}")
    print("-" * 90)
    for r in tws_results:
        print(f"{r['symbol']:7s} | {r['timeframe']:4s} | {r['strategy_id']:22s} | {r['is_sharpe']:9.2f} | {r['oos_sharpe']:10.2f} | {r['status']:10s}")
    print("=" * 90)
    print(f"\nSaved report to {report_file}\n")


if __name__ == "__main__":
    main()
