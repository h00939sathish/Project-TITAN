"""Backtest the live session's strategy (ma-crossover 5/20, 5-min bars) on real
TWS history through the REAL PaperTradingEngine (ReplayEngine + BacktestAdapter
+ conservative fill model). One run per instrument (the strategy is stateful).

Run:  python scripts/backtest_tws_session.py [--symbol SPY]
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from titan.backtest.engine import ReplayEngine
from titan.data.forex_pairs import FOREX_SYMBOLS
from titan.research.harness import make_ma_signal_fn

HISTORY = Path(__file__).resolve().parents[1] / "research" / "tws_history"
SYMBOLS = ["SPY", "QQQ", "IWM", "EURUSD", "GBPUSD", "AAPL", "MSFT", "XLF", "XLK"]
PARAMS = {"fast": 5, "slow": 20}
SLIPPAGE_BPS = 1.0
COMMISSION_BPS = 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()
    symbols = [args.symbol] if args.symbol else SYMBOLS

    print("=" * 92)
    print("BACKTEST — ma-crossover(5,20) on real TWS 5-min RTH bars, through the real engine")
    print(f"slippage={SLIPPAGE_BPS}bps commission={COMMISSION_BPS}bps | 2026-06 -> 2026-07-31")
    print("=" * 92)

    rows = []
    for sym in symbols:
        path = HISTORY / f"{sym}.json"
        if not path.exists():
            print(f"{sym}: no history file (run pull_tws_history.py first)")
            continue
        bars = json.loads(path.read_text(encoding="utf-8"))
        if not bars:
            print(f"{sym}: empty history")
            continue

        qty = 1000 if sym in FOREX_SYMBOLS else 1
        first = bars[0]["close"]
        last = bars[-1]["close"]
        bh_pct = (last - first) / first * 100

        strategy = make_ma_signal_fn(dict(PARAMS)).strat  # MovingAverageCrossover instance
        engine = ReplayEngine(
            strategy, bars,
            slippage_bps=SLIPPAGE_BPS, commission_bps=COMMISSION_BPS,
            intent_qty=qty,
        )
        result = engine.run()

        pnl = float(result.total_pnl)
        start_cash = 100000.0
        ret_pct = pnl / start_cash * 100
        rows.append((sym, len(bars), result.trades, result.rejected_intents,
                     round(pnl, 2), round(ret_pct, 3), round(bh_pct, 2)))

    print(f"\n{'SYM':<8}{'BARS':>6}{'TRADES':>7}{'REJ':>5}{'PNL$':>12}{'RET%':>9}{'BUYHOLD%':>10}")
    print("-" * 92)
    for r in rows:
        print(f"{r[0]:<8}{r[1]:>6}{r[2]:>7}{r[3]:>5}{r[4]:>12.2f}{r[5]:>9.3f}{r[6]:>10.2f}")

    if rows:
        tot_pnl = sum(r[4] for r in rows)
        tot_trades = sum(r[2] for r in rows)
        print("-" * 92)
        print(f"{'TOTAL':<8}{'':>6}{tot_trades:>7}{'':>5}{tot_pnl:>12.2f}{'':>9}{'':>10}")
        print("\nCaveats: 2 months of RTH bars; strategy-level sizing (1 sh / 1000 fx);")
        print("the paper account's funding asymmetry (BUY >~$100 rejects, SELL fills) is")
        print("an operational constraint, not modeled here.")


if __name__ == "__main__":
    main()
