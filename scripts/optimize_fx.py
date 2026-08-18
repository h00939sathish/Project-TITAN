"""Optimize parameters for top FX strategies using the new clean Dukascopy datasets.

Focusing on:
- Mean Reversion (Daily)
- Bollinger (Daily)
- TraderDev EMA9xVWAP (4h from 5m)
"""

import json
import sys
import itertools
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from titan.research.harness import (
    StrategyRunner,
    make_mr_signal_fn,
    make_bollinger_signal_fn,
    make_traderdev_ema9vwap_signal_fn,
)
from titan.backtest.results import BacktestResult

FX_CLEAN_DAILY_DIR = ROOT_DIR / "research" / "fx_clean_daily"
FX_CLEAN_5M_DIR = ROOT_DIR / "research" / "fx_clean_5m"


def load_json_bars(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bars = []
    for r in data:
        bars.append({
            "timestamp": r.get("timestamp", r.get("date", "")),
            "open": float(r["open"]),
            "high": float(r.get("high", r["close"])),
            "low": float(r.get("low", r["close"])),
            "close": float(r["close"]),
            "volume": int(float(r.get("volume", r.get("n", 0)))),
        })
    bars.sort(key=lambda b: b["timestamp"])
    return bars

def resample_bars(bars: list[dict], target_minutes: int) -> list[dict]:
    if not bars: return []
    resampled = []
    bucket = None
    bucket_key = None
    for bar in bars:
        ts_str = bar["timestamp"]
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError: continue
        epoch_min = int(ts.timestamp()) // 60
        aligned = (epoch_min // target_minutes) * target_minutes
        key = str(aligned)
        if key != bucket_key:
            if bucket is not None: resampled.append(bucket)
            bucket = {
                "timestamp": ts_str, "open": bar["open"], "high": bar["high"],
                "low": bar["low"], "close": bar["close"], "volume": bar["volume"],
            }
            bucket_key = key
        else:
            bucket["high"] = max(bucket["high"], bar["high"])
            bucket["low"] = min(bucket["low"], bar["low"])
            bucket["close"] = bar["close"]
            bucket["volume"] += bar["volume"]
            bucket["timestamp"] = ts_str
    if bucket is not None: resampled.append(bucket)
    return resampled

def run_optimization(strategy_name: str, factory, bars: list[dict], param_grid: dict, slippage_bps=0.3):
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))
    
    print(f"\n--- Optimizing {strategy_name} ({len(combinations)} combinations) ---")
    
    results = []
    for combo in combinations:
        params = dict(zip(keys, combo))
        sig_fn = factory(params)
        runner = StrategyRunner(
            sig_fn,
            notional_allocation_pct=10.0,
            slippage_bps=slippage_bps,
            commission_bps=0.5,
        )
        eq, trades = runner.run(bars)
        res = BacktestResult.compute(eq, trades)
        if res.total_trades > 0:
            results.append({
                "params": params,
                "sharpe": res.sharpe_ratio,
                "return": res.total_return_pct,
                "trades": res.total_trades,
                "win_rate": res.win_rate,
                "pf": res.profit_factor
            })
            
    # Sort by Sharpe ratio
    results.sort(key=lambda x: x["sharpe"], reverse=True)
    
    print("Top 5 configurations by Sharpe Ratio:")
    print(f"{'Sharpe':>7s} | {'Return':>7s} | {'Trades':>6s} | {'Win %':>6s} | {'PF':>5s} | Params")
    print("-" * 80)
    for r in results[:5]:
        p_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        print(f"{r['sharpe']:7.2f} | {r['return']:+6.2f}% | {r['trades']:6d} | {r['win_rate']:5.1f}% | {r['pf']:5.2f} | {p_str}")

def main():
    # 1. Mean Reversion on GBPUSD Daily
    path_gbp_daily = FX_CLEAN_DAILY_DIR / "GBPUSD.json"
    if path_gbp_daily.exists():
        bars_daily = load_json_bars(path_gbp_daily)
        mr_grid = {
            "window": [10, 20, 30],
            "entry_z": [-1.5, -2.0, -2.5],
            "exit_z": [-0.5, 0.0, 0.5]
        }
        run_optimization("Mean Reversion (GBPUSD Daily)", make_mr_signal_fn, bars_daily, mr_grid)

    # 2. Bollinger on EURUSD Daily
    path_eur_daily = FX_CLEAN_DAILY_DIR / "EURUSD.json"
    if path_eur_daily.exists():
        bars_eur_daily = load_json_bars(path_eur_daily)
        bollinger_grid = {
            "window": [15, 20, 25],
            "std_dev_multiplier": [1.5, 2.0, 2.5]
        }
        run_optimization("Bollinger (EURUSD Daily)", make_bollinger_signal_fn, bars_eur_daily, bollinger_grid)

    # 3. EMA9xVWAP on GBPUSD 4h
    path_gbp_5m = FX_CLEAN_5M_DIR / "GBPUSD.json"
    if path_gbp_5m.exists():
        bars_gbp_5m = load_json_bars(path_gbp_5m)
        bars_gbp_4h = resample_bars(bars_gbp_5m, 240)
        ema_grid = {
            "ema_period": [5, 9, 13],
            "vwap_period": [120, 240, 360],
            "atr_period": [14],
            "trail_mult": [2.0, 3.0, 4.0]
        }
        run_optimization("TraderDev EMA9xVWAP (GBPUSD 4h)", make_traderdev_ema9vwap_signal_fn, bars_gbp_4h, ema_grid)

if __name__ == "__main__":
    main()
