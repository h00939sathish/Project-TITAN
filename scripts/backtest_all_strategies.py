"""Backtest all 10 registered TITAN strategies across history datasets with realistic cost modeling and full OHLCV inputs."""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import titan.strategies.registrations  # noqa: F401
from titan.strategies.registry import get_registry
from titan.research.harness import StrategyRunner, buy_and_hold_result, INITIAL_CAPITAL
from titan.backtest.results import BacktestResult

TWS_HISTORY_DIR = ROOT_DIR / "research" / "tws_history"
TWS_DAILY_DIR = ROOT_DIR / "research" / "tws_daily"
SPY_DAILY_CSV = ROOT_DIR / "tests" / "fixtures" / "market" / "real_spy_2020_2024.csv"

STRATEGY_DEFAULT_PARAMS = {
    "ma-crossover": {"fast": 5, "slow": 20},
    "mean-reversion": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
    "volatility-regime": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
    "time-series-momentum": {"lookback": 20},
    "dual-ma": {"fast": 5, "slow": 20},
    "rsi": {"window": 14, "oversold": 30.0, "overbought": 70.0},
    "bollinger": {"window": 20, "std_dev_multiplier": 2.5},
    "orb": {"atr_period": 14, "min_volume_ratio": 1.2, "breakout_mult": 1.0},
    "vwap-reversion": {"window": 30, "std_dev": 2.0},
    "traderdev-ema9-vwap": {"ema_period": 9, "vwap_period": 120, "atr_period": 14, "trail_mult": 3.0},
}


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


def run_backtest(bars: list[dict], strategy_id: str, params: dict,
                 slippage_bps: float = 0.5, commission_bps: float = 1.0) -> dict:
    reg = get_registry()
    entry = reg.get(strategy_id)
    runner = StrategyRunner(
        signal_fn,
        notional_allocation_pct=10.0,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
    )
    eq, trades = runner.run(bars)
    
    res = BacktestResult.compute(eq, trades)
    bh = buy_and_hold_result(bars)
    
    return {
        "strategy_id": strategy_id,
        "params": params,
        "total_return_pct": round(res.total_return_pct, 2),
        "sharpe_ratio": round(res.sharpe_ratio, 2),
        "max_drawdown_pct": round(res.max_drawdown_pct, 2),
        "win_rate_pct": round(res.win_rate, 2),
        "profit_factor": round(res.profit_factor, 2) if res.profit_factor < 100 else 999.0,
        "total_trades": res.total_trades,
        "buy_and_hold_return_pct": round(bh.total_return_pct, 2),
        "vs_buy_and_hold_pct": round(res.total_return_pct - bh.total_return_pct, 2),
    }


def main():
    datasets = []
    
    # 1. Add 5m intraday TWS history files
    if TWS_HISTORY_DIR.exists():
        for p in TWS_HISTORY_DIR.glob("*.json"):
            datasets.append((f"{p.stem} [5m Intraday]", load_json_bars(p)))
            
    # 2. Add Daily SPY fixture
    if SPY_DAILY_CSV.exists():
        from titan.data.ingest import read_csv
        raw = read_csv(SPY_DAILY_CSV)
        spy_daily_bars = [{
            "timestamp": r["date"],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": int(float(r.get("volume", 0))),
        } for r in raw]
        spy_daily_bars.sort(key=lambda b: b["timestamp"])
        datasets.append(("SPY [Daily 2020-2024]", spy_daily_bars))
        
    # 3. Add FX Daily datasets
    for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
        p = TWS_DAILY_DIR / f"{symbol}.json"
        if p.exists():
            datasets.append((f"{symbol} [Daily History]", load_json_bars(p)))
            
    print(f"Loaded {len(datasets)} datasets for backtesting.\n")
    
    all_results = {}
    
    for dataset_name, bars in datasets:
        print(f"==========================================================================")
        print(f"  Dataset: {dataset_name} ({len(bars)} bars, {bars[0]['timestamp'][:10]} to {bars[-1]['timestamp'][:10]})")
        print(f"==========================================================================")
        
        bh = buy_and_hold_result(bars)
        print(f"  Buy & Hold Return: {bh.total_return_pct:+.2f}% | Sharpe: {bh.sharpe_ratio:.2f} | Max DD: {bh.max_drawdown_pct:.1f}%\n")
        
        ds_results = []
        for sid, params in STRATEGY_DEFAULT_PARAMS.items():
            try:
                res = run_backtest(bars, sid, params)
                ds_results.append(res)
                print(f"  {sid:25s} | Ret: {res['total_return_pct']:+6.2f}% | Sharpe: {res['sharpe_ratio']:5.2f} | DD: {res['max_drawdown_pct']:5.2f}% | Win: {res['win_rate_pct']:5.1f}% | Trades: {res['total_trades']:3d} | vs B&H: {res['vs_buy_and_hold_pct']:+6.2f}%")
            except Exception as e:
                print(f"  {sid:25s} | ERROR: {e}")
                
        all_results[dataset_name] = ds_results
        print()
        
    # Write JSON summary artifact
    out_file = ROOT_DIR / "research" / "backtest_results_summary.json"
    out_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"Saved complete backtest results to {out_file}")


if __name__ == "__main__":
    main()
