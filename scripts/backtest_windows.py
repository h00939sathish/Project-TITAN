"""Compare strategies across time windows: first half, second half, full run."""
import argparse, sys
from dotenv import load_dotenv
from titan.data.alpaca_feed import AlpacaDataFeed
from titan.research.harness import StrategyRunner, buy_and_hold_result, INITIAL_CAPITAL
from titan.strategies.registrations import _reg

STRATEGIES = {
    "ma-crossover":       {"fast": 10, "slow": 20},
    "dual-ma":            {"fast": 20, "slow": 50},
    "time-series-momentum": {"lookback": 50},
    "volatility-regime":  {"vol_window": 20, "median_window": 30, "vol_multiple": 1.0},
    "mean-reversion":     {"window": 10, "entry_z": -2.0, "exit_z": -0.5},
}

def _calc_qty(capital, price, pct):
    return max(1, int(capital * (pct / 100) / price))

def run(label, bars, capital_pct):
    price = bars[0]["close"]
    qty = _calc_qty(INITIAL_CAPITAL, price, capital_pct)
    bh = buy_and_hold_result(bars)
    print(f"\n  {label} ({bars[0]['timestamp'][:10]} to {bars[-1]['timestamp'][:10]}, {len(bars)} bars)")
    print(f"    BH: {bh.total_return_pct:+.2f}%  Sharpe={bh.sharpe_ratio:.2f}  DD={bh.max_drawdown_pct:.1f}%")
    for sid, params in STRATEGIES.items():
        reg = _reg.get(sid)
        fn = reg.factory(params)
        runner = StrategyRunner(fn, buy_qty=qty)
        eq, trades = runner.run(bars)
        r = round((eq[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2)
        print(f"    {sid:25s}  return={r:+.2f}%  trades={len(trades)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default="SPY,QQQ,AAPL,MSFT")
    parser.add_argument("--capital-pct", type=float, default=25.0)
    args = parser.parse_args()

    load_dotenv()
    instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]
    feed = AlpacaDataFeed(paper=True)

    for sym in instruments:
        bars = feed.fetch_to_approved(sym)
        if not bars:
            continue
        mid = len(bars) // 2
        q1 = len(bars) // 4
        q3 = q1 * 3
        run(f"=== {sym} FULL ===", bars, args.capital_pct)
        run(f"--- {sym} first half ---", bars[:mid], args.capital_pct)
        run(f"--- {sym} second half ---", bars[mid:], args.capital_pct)
        run(f"--- {sym} first Q ---", bars[:q1], args.capital_pct)
        run(f"--- {sym} mid half ---", bars[q1:q3], args.capital_pct)
        run(f"--- {sym} last Q ---", bars[q3:], args.capital_pct)

if __name__ == "__main__":
    main()
