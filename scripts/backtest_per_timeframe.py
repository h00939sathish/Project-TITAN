"""Backtest all 10 TITAN strategies at their DESIGN-INTENDED timeframes.

Each strategy is matched to the timeframe and dataset(s) that fit its logic:
  - ORB:                  15m intraday (equities with volume)
  - VWAP-reversion:       5m intraday  (equities with volume)
  - TraderDev EMA9×VWAP:  4h           (FX pairs, resampled from 5m)
  - Mean-reversion:       1d           (long daily history)
  - Time-series-momentum: 1d           (long daily history)
  - MA-crossover:         1d           (long daily history)
  - Dual-MA:              1d           (long daily history)
  - RSI:                  1d           (long daily history)
  - Bollinger:            1d           (long daily history)
  - Volatility-regime:    1d           (long daily history)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import titan.strategies.registrations  # noqa: F401 — register all strategies
from titan.strategies.registry import get_registry
from titan.research.harness import StrategyRunner, buy_and_hold_result, INITIAL_CAPITAL
from titan.backtest.results import BacktestResult

# ─── Data paths ──────────────────────────────────────────────────────────────

TWS_HISTORY_DIR = ROOT_DIR / "research" / "tws_history"       # 5m bars
TWS_DAILY_DIR   = ROOT_DIR / "research" / "tws_daily"         # daily bars (FX)
SPY_DAILY_CSV   = ROOT_DIR / "tests" / "fixtures" / "market" / "real_spy_2020_2024.csv"
FX_CLEAN_5M_DIR = ROOT_DIR / "research" / "fx_clean_5m"       # Dukascopy 5m midpoint bars
FX_CLEAN_DAILY_DIR = ROOT_DIR / "research" / "fx_clean_daily" # Dukascopy Daily midpoint bars

# ─── Strategy → Timeframe mapping ────────────────────────────────────────────

STRATEGY_CONFIGS = {
    # Intraday strategies — need resampled bars
    "orb": {
        "timeframe": "15m",
        "resample_from": "5m",
        "resample_minutes": 15,
        "params": {"atr_period": 14, "min_volume_ratio": 1.2, "breakout_mult": 1.0},
        "needs_volume": True,
        "datasets": "intraday_equity",  # equities only (have real volume)
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    "vwap-reversion": {
        "timeframe": "5m",
        "resample_from": None,  # native 5m
        "resample_minutes": None,
        "params": {"window": 30, "std_dev": 2.0},
        "needs_volume": True,
        "datasets": "intraday_equity",
        "slippage_bps": 0.5,
        "commission_bps": 1.0,
    },
    "traderdev-ema9-vwap": {
        "timeframe": "4h",
        "resample_from": "5m",
        "resample_minutes": 240,
        "params": {"ema_period": 9, "vwap_period": 120, "atr_period": 14, "trail_mult": 3.0},
        "needs_volume": False,
        "datasets": "intraday_fx",  # FX pairs (design-noted @4h)
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    # Daily strategies — use long daily history
    "mean-reversion": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "time-series-momentum": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"lookback": 20},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "ma-crossover": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"fast": 5, "slow": 20},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "dual-ma": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"fast": 5, "slow": 20},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "rsi": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"window": 14, "oversold": 30.0, "overbought": 70.0},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "bollinger": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"window": 20, "std_dev_multiplier": 2.5},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
    "volatility-regime": {
        "timeframe": "1d",
        "resample_from": None,
        "resample_minutes": None,
        "params": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
        "needs_volume": False,
        "datasets": "daily",
        "slippage_bps": 0.3,
        "commission_bps": 0.5,
    },
}

# Equity symbols in tws_history (have real volume)
EQUITY_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "IWM", "XLF", "XLK"]
# FX symbols with clean Dukascopy data
FX_CLEAN_SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD"]


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_json_bars(path: Path) -> list[dict]:
    """Load JSON bar data with OHLCV normalization."""
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
            "volume": max(0, int(float(r.get("volume", r.get("n", 0))))),
        })
    bars.sort(key=lambda b: b["timestamp"])
    return bars


def load_spy_daily_csv() -> list[dict]:
    """Load SPY daily CSV via ingest pipeline."""
    from titan.data.ingest import read_csv
    raw = read_csv(SPY_DAILY_CSV)
    bars = [{
        "timestamp": r["date"],
        "open": float(r["open"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
        "close": float(r["close"]),
        "volume": int(float(r.get("volume", 0))),
    } for r in raw]
    bars.sort(key=lambda b: b["timestamp"])
    return bars


# ─── Bar resampling ──────────────────────────────────────────────────────────

def resample_bars(bars: list[dict], target_minutes: int) -> list[dict]:
    """Resample 5-minute bars to a higher timeframe (15m, 1h, 4h).

    Alignment: floor(timestamp / target_minutes). Preserves OHLCV semantics:
      open  = first bar's open
      high  = max of constituent highs
      low   = min of constituent lows
      close = last bar's close
      volume = sum of constituent volumes
    """
    if not bars:
        return []

    resampled = []
    bucket: dict | None = None
    bucket_key: str | None = None

    for bar in bars:
        ts_str = bar["timestamp"]
        # Parse ISO timestamp
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        # Compute bucket key: floor to target_minutes
        epoch_min = int(ts.timestamp()) // 60
        aligned = (epoch_min // target_minutes) * target_minutes
        key = str(aligned)

        if key != bucket_key:
            # Emit previous bucket
            if bucket is not None:
                resampled.append(bucket)
            bucket = {
                "timestamp": ts_str,
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
            bucket_key = key
        else:
            # Accumulate into current bucket
            bucket["high"] = max(bucket["high"], bar["high"])
            bucket["low"] = min(bucket["low"], bar["low"])
            bucket["close"] = bar["close"]
            bucket["volume"] += bar["volume"]
            bucket["timestamp"] = ts_str  # last bar's timestamp

    if bucket is not None:
        resampled.append(bucket)

    return resampled


# ─── Backtest runner ──────────────────────────────────────────────────────────

def run_backtest(bars: list[dict], strategy_id: str, params: dict,
                 slippage_bps: float = 0.5, commission_bps: float = 1.0,
                 cost_model=None) -> dict:
    """Run a single strategy backtest and return summary metrics."""
    reg = get_registry()
    entry = reg.get(strategy_id)
    signal_fn = entry.factory(params)

    runner = StrategyRunner(
        signal_fn,
        notional_allocation_pct=10.0,
        slippage_bps=slippage_bps,
        commission_bps=commission_bps,
        cost_model=cost_model,
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


# ─── Dataset builders ────────────────────────────────────────────────────────

def build_datasets_for_strategy(strategy_id: str, cfg: dict) -> list[tuple[str, list[dict]]]:
    """Build the list of (label, bars) datasets appropriate for the strategy."""
    datasets = []
    ds_type = cfg["datasets"]
    target_min = cfg.get("resample_minutes")

    if ds_type == "intraday_equity":
        for sym in EQUITY_SYMBOLS:
            path = TWS_HISTORY_DIR / f"{sym}.json"
            if path.exists():
                raw_bars = load_json_bars(path)
                if target_min:
                    bars = resample_bars(raw_bars, target_min)
                    label = f"{sym} [{cfg['timeframe']} from 5m, {len(bars)} bars]"
                else:
                    bars = raw_bars
                    label = f"{sym} [5m native, {len(bars)} bars]"
                if bars:
                    datasets.append((label, bars))

    elif ds_type == "intraday_fx":
        for sym in FX_CLEAN_SYMBOLS:
            path = FX_CLEAN_5M_DIR / f"{sym}.json"
            if path.exists():
                raw_bars = load_json_bars(path)
                if target_min:
                    bars = resample_bars(raw_bars, target_min)
                    label = f"{sym} [{cfg['timeframe']} from clean 5m, {len(bars)} bars]"
                else:
                    bars = raw_bars
                    label = f"{sym} [clean 5m native, {len(bars)} bars]"
                if bars:
                    datasets.append((label, bars))

    elif ds_type == "daily":
        # SPY daily (long history, has volume)
        if SPY_DAILY_CSV.exists():
            spy_bars = load_spy_daily_csv()
            if spy_bars:
                datasets.append((f"SPY [Daily 2020-2024, {len(spy_bars)} bars]", spy_bars))

        # FX daily (clean Dukascopy history)
        for sym in FX_CLEAN_SYMBOLS:
            path = FX_CLEAN_DAILY_DIR / f"{sym}.json"
            if path.exists():
                bars = load_json_bars(path)
                if bars:
                    datasets.append((f"{sym} [Clean Daily, {len(bars)} bars]", bars))

    return datasets


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("  TITAN Per-Timeframe Backtest — Each strategy at its design-intended timeframe")
    print("=" * 90)
    print()

    all_results = {}

    for sid, cfg in STRATEGY_CONFIGS.items():
        tf = cfg["timeframe"]
        print(f"╔{'═' * 88}╗")
        print(f"║  Strategy: {sid:30s}  Timeframe: {tf:5s}  Volume Req: {str(cfg['needs_volume']):5s}  ║")
        print(f"╚{'═' * 88}╝")

        datasets = build_datasets_for_strategy(sid, cfg)
        if not datasets:
            print(f"  ⚠ No suitable datasets found for {sid} at {tf}\n")
            continue

        strategy_results = []
        for ds_label, bars in datasets:
            bh = buy_and_hold_result(bars)
            print(f"  ┌─ {ds_label}")
            print(f"  │  B&H: {bh.total_return_pct:+.2f}% | Sharpe: {bh.sharpe_ratio:.2f} | DD: {bh.max_drawdown_pct:.1f}%")

            try:
                res = run_backtest(bars, sid, cfg["params"],
                                   slippage_bps=cfg["slippage_bps"],
                                   commission_bps=cfg["commission_bps"])
                res["timeframe"] = tf
                res["dataset"] = ds_label
                strategy_results.append(res)

                # Color-code the result
                ret = res["total_return_pct"]
                sharpe = res["sharpe_ratio"]
                vs_bh = res["vs_buy_and_hold_pct"]
                verdict = "✓" if ret > 0 and sharpe > 0 else "✗"

                print(f"  │  {verdict} Ret: {ret:+7.2f}% | Sharpe: {sharpe:5.2f} | "
                      f"DD: {res['max_drawdown_pct']:5.2f}% | Win: {res['win_rate_pct']:5.1f}% | "
                      f"Trades: {res['total_trades']:4d} | PF: {res['profit_factor']:5.2f} | "
                      f"vs B&H: {vs_bh:+6.2f}%")
            except Exception as e:
                print(f"  │  ✗ ERROR: {e}")
            print(f"  └{'─' * 80}")

        all_results[sid] = strategy_results
        print()

    # ─── Summary Table ────────────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("  SUMMARY: Best result per strategy (across datasets)")
    print("=" * 90)
    print(f"  {'Strategy':30s} {'TF':5s} {'Best Dataset':35s} {'Return':>8s} {'Sharpe':>7s} {'Trades':>7s}")
    print(f"  {'-' * 30} {'-' * 5} {'-' * 35} {'-' * 8} {'-' * 7} {'-' * 7}")

    for sid, results in all_results.items():
        if not results:
            print(f"  {sid:30s} {'—':5s} {'no data':35s} {'—':>8s} {'—':>7s} {'—':>7s}")
            continue
        # Best by Sharpe ratio
        best = max(results, key=lambda r: r["sharpe_ratio"])
        ds_short = best["dataset"][:35]
        print(f"  {sid:30s} {best['timeframe']:5s} {ds_short:35s} "
              f"{best['total_return_pct']:+7.2f}% {best['sharpe_ratio']:6.2f} "
              f"{best['total_trades']:6d}")

    # ─── Save results ─────────────────────────────────────────────────────────
    out_file = ROOT_DIR / "research" / "backtest_per_timeframe_results.json"
    out_file.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n  Results saved to {out_file}")


if __name__ == "__main__":
    main()
