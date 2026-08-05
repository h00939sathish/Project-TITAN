"""Short-capable backtest: dual-ma, momentum, vol-regime can go short."""
import argparse
from dotenv import load_dotenv
from titan.data.alpaca_feed import AlpacaDataFeed
from titan.research.harness import INITIAL_CAPITAL
from titan.strategies.registrations import _reg

class ShortRunner:
    """Long/short signal runner. BUY=want long, SELL=want short."""
    def __init__(self, signal_fn, qty=10, slippage_bps=0.5, commission_bps=1.0):
        self.signal_fn = signal_fn
        self.qty = qty
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps

    def _fill_cost(self, price, qty, side):
        slip = price * self.slippage_bps / 10000
        comm = price * self.commission_bps / 10000
        if side == "buy":
            return qty * (price + slip + comm)
        return qty * (price - slip - comm)

    def run(self, bars):
        cash = INITIAL_CAPITAL
        pos = 0  # shares, positive=long, negative=short
        pos_price = 0.0
        trades = []
        eq = [INITIAL_CAPITAL]

        for bar in bars:
            sig = self.signal_fn(bar)
            price = bar["close"]
            qty = self.qty

            if sig == "BUY":
                if pos < 0:
                    # cover short flip to long
                    cost = self._fill_cost(price, qty, "buy")
                    if cost <= cash:
                        pnl = (pos_price - price) * abs(pos)  # short pnl
                        cash -= cost
                        pos = qty
                        pos_price = cost / qty
                        trades.append({"side":"flip_long","pnl":pnl})
                elif pos == 0:
                    cost = self._fill_cost(price, qty, "buy")
                    if cost <= cash:
                        cash -= cost
                        pos = qty
                        pos_price = cost / qty
                        trades.append({"side":"long","pnl":0})
            elif sig == "SELL":
                if pos > 0:
                    # exit long flip to short
                    proceeds = self._fill_cost(price, qty, "sell")
                    pnl = (price - pos_price) * pos
                    cash += proceeds
                    pos = -qty
                    pos_price = price
                    trades.append({"side":"flip_short","pnl":pnl})
                elif pos == 0:
                    proceeds = self._fill_cost(price, qty, "sell")
                    cash += proceeds
                    pos = -qty
                    pos_price = price
                    trades.append({"side":"short","pnl":0})

            mtm = cash + pos * price if pos != 0 else cash
            eq.append(mtm)

        return eq, trades

STRATS = {
    "dual-ma":            {"fast": 20, "slow": 50},
    "time-series-momentum": {"lookback": 50},
    "ma-crossover":       {"fast": 10, "slow": 20},
    "volatility-regime":  {"vol_window": 20, "median_window": 30, "vol_multiple": 1.0},
    "mean-reversion":     {"window": 10, "entry_z": -2.0, "exit_z": -0.5},
}

def run(label, bars):
    price = bars[0]["close"]
    qty = max(1, int(INITIAL_CAPITAL * 0.25 / price))
    bh_r = round((bars[-1]["close"] / bars[0]["close"] - 1) * 100, 2)
    print(f"\n  {label} ({len(bars)} bars)  BH: {bh_r:+.2f}%")
    for sid, params in STRATS.items():
        fn = _reg.get(sid).factory(params)
        runner = ShortRunner(fn, qty=qty)
        eq, trades = runner.run(bars)
        r = round((eq[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 2)
        flips = sum(1 for t in trades if "flip" in t["side"])
        print(f"    {sid:25s}  return={r:+.2f}%  actions={len(trades)}  flips={flips}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruments", default="SPY,QQQ,AAPL,MSFT")
    args = parser.parse_args()
    load_dotenv()
    feed = AlpacaDataFeed(paper=True)
    for sym in [s.strip() for s in args.instruments.split(",") if s.strip()]:
        bars = feed.fetch_to_approved(sym)
        if bars:
            run(f"=== {sym} ===", bars)

if __name__ == "__main__":
    main()
