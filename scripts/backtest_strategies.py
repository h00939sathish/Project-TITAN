"""Run all registered strategies over CSV data, print metrics, parameter sweep."""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor

from titan.data.ingest import read_csv
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from titan.backtest.corporate_actions import common_adjustments
from titan.research.harness import (
    StrategyRunner,
    buy_and_hold_result,
    cash_result,
    make_ma_signal_fn,
    make_mr_signal_fn,
    make_momentum_signal_fn,
    make_vol_regime_signal_fn,
    make_dual_ma_signal_fn,
    INITIAL_CAPITAL,
)
from dotenv import load_dotenv
import titan.strategies.registrations  # noqa: F401
from titan.strategies.registry import get_registry
from titan.data.alpaca_feed import AlpacaDataFeed


STRATEGIES = {
    "ma-crossover": make_ma_signal_fn,
    "mean-reversion": make_mr_signal_fn,
    "time-series-momentum": make_momentum_signal_fn,
    "volatility-regime": make_vol_regime_signal_fn,
    "dual-ma": make_dual_ma_signal_fn,
}

DEFAULT_PARAMS = {
    "ma-crossover": {"fast": 5, "slow": 20},
    "mean-reversion": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
    "time-series-momentum": {"lookback": 20},
    "volatility-regime": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
    "dual-ma": {"fast": 5, "slow": 20},
}

PARAM_GRIDS = {
    "ma-crossover": [
        {"fast": f, "slow": s} for f in (2, 5, 10, 20) for s in (10, 20, 50, 100) if f < s
    ],
    "mean-reversion": [
        {"window": w, "entry_z": -2.0, "exit_z": -0.5}
        for w in (10, 20, 30, 50)
    ],
    "time-series-momentum": [
        {"lookback": lb} for lb in (5, 10, 20, 50, 100)
    ],
    "volatility-regime": [
        {"vol_window": vw, "median_window": mw, "vol_multiple": 1.0}
        for vw in (10, 20, 30) for mw in (30, 60, 90) if vw < mw
    ],
    "dual-ma": [
        {"fast": f, "slow": s} for f in (2, 5, 10, 20) for s in (10, 20, 50, 100) if f < s
    ],
}


def load_bars(path: str) -> list[dict]:
    raw = read_csv(path)
    if not raw:
        raise ValueError(f"No data in {path}")
    report, good = validate_and_quarantine(raw, normalize_row, pass_through_unknown=True)
    ca_db = common_adjustments()
    return ca_db.adjust_bars(good)


def _calc_qty(capital: float, price: float, capital_pct: float) -> int:
    return max(1, int(capital * capital_pct / 100 / price))


def run_strategy(bars: list[dict], signal_factory, params: dict, capital_pct: float = 25.0) -> dict:
    runner = StrategyRunner(signal_factory(params), notional_allocation_pct=capital_pct)
    eq, trades = runner.run(bars)
    end = eq[-1]
    total_return = (end - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    bh = buy_and_hold_result(bars)
    bh_ret = bh.total_return_pct
    return {
        "trades": len(trades),
        "total_return_pct": round(total_return, 2),
        "buy_hold_pct": round(bh_ret, 2),
        "vs_bh": round(total_return - bh_ret, 2),
    }


def _run_one(params_and_factory):
    params, factory_fn, capital_pct = params_and_factory
    try:
        runner = StrategyRunner(factory_fn(params), notional_allocation_pct=capital_pct)
        eq, trades = runner.run(_bars_global)
        end = eq[-1]
        total_return = round((end - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2)
        return (params, total_return, len(trades))
    except Exception as e:
        return (params, None, 0)


_bars_global = None



def main():
    parser = argparse.ArgumentParser(description="Backtest strategies over CSV data")
    parser.add_argument("data_file", nargs="?", default=None, help="CSV file with market data")
    parser.add_argument("--strategy", default=None, help="Run only this strategy (default: all)")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--parallel", action="store_true", help="Run sweep in parallel")
    parser.add_argument("--capital-pct", type=float, default=25.0,
                        help="Percent of capital deployed per entry (default: 25%%)")
    parser.add_argument("--live-data", action="store_true", help="Fetch data from Alpaca API")
    parser.add_argument("--instruments", default="SPY,QQQ",
                        help="Comma-separated symbols for --live-data (default: SPY,QQQ)")
    args = parser.parse_args()

    if args.live_data:
        load_dotenv()
        instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]
        feed = AlpacaDataFeed(paper=True)
        all_bars: list[tuple[str, list[dict]]] = []
        for sym in instruments:
            bars = feed.fetch_to_approved(sym)
            if not bars:
                print(f"  No data for {sym}, skipping")
                continue
            all_bars.append((sym, bars))
            price = bars[0]["close"]
            qty = _calc_qty(INITIAL_CAPITAL, price, args.capital_pct)
            first, last = bars[0]["timestamp"][:10], bars[-1]["timestamp"][:10]
            print(f"  {sym}: {len(bars)} bars ({first} to {last}), price={price:.2f}, qty={qty}")
        print()
    elif args.data_file:
        bars = load_bars(args.data_file)
        all_bars = [("", bars)]
        print(f"Loaded {len(bars)} bars ({bars[0]['timestamp'][:10]} to {bars[-1]['timestamp'][:10]})")
    else:
        print("Provide a data_file or use --live-data")
        sys.exit(1)

    strategies_to_run = [args.strategy] if args.strategy else list(STRATEGIES)

    for label, bars in all_bars:
        global _bars_global
        _bars_global = bars

        bh = buy_and_hold_result(bars)
        cash_r = cash_result(bars)
        header = f"=== {label} ===" if label else "=== Results ==="
        print(f"\n{header}")
        print(f"  Bars: {len(bars)} ({bars[0]['timestamp'][:10]} to {bars[-1]['timestamp'][:10]})")
        print(f"  Buy & Hold:  {bh.total_return_pct:+.2f}%  Sharpe={bh.sharpe_ratio:.2f}  DD={bh.max_drawdown_pct:.1f}%")
        print(f"  Cash:        {cash_r.total_return_pct:+.2f}%")

        print(f"\n  --- Default params ---")
        for sid in strategies_to_run:
            factory = STRATEGIES.get(sid)
            if not factory:
                print(f"    Unknown: {sid}")
                continue
            params = DEFAULT_PARAMS[sid]
            result = run_strategy(bars, factory, params, args.capital_pct)
            print(f"    {sid:25s}  {result}")

        if args.sweep:
            print(f"\n  --- Parameter sweep ---")
            for sid in strategies_to_run:
                factory = STRATEGIES.get(sid)
                grid = PARAM_GRIDS.get(sid, [DEFAULT_PARAMS[sid]])
                price = bars[0]["close"]
                qty = _calc_qty(INITIAL_CAPITAL, price, args.capital_pct)
                if args.parallel and len(grid) > 1:
                    inputs = [(p, factory, qty) for p in grid]
                    with ProcessPoolExecutor(max_workers=8) as pool:
                        results = pool.map(_run_one, inputs)
                        sorted_results = sorted(results, key=lambda x: x[1] or -999, reverse=True)
                else:
                    results = []
                    for params in grid:
                        try:
                            runner = StrategyRunner(factory(params), notional_allocation_pct=args.capital_pct)
                            eq, trades = runner.run(bars)
                            tr = round((eq[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2)
                            results.append((params, tr, len(trades)))
                        except Exception as e:
                            results.append((params, None, 0))
                    sorted_results = sorted(results, key=lambda x: x[1] or -999, reverse=True)

                print(f"\n    {sid} — top 5 of {len(grid)}:")
                for params, tr, trades in sorted_results[:5]:
                    p_str = ",".join(f"{k}={v}" for k, v in params.items())
                    print(f"      {p_str:40s}  return={tr:+.2f}%  trades={trades}")


if __name__ == "__main__":
    main()
