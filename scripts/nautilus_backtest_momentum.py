#!/usr/bin/env python3
"""Cross-validate TITAN's TimeSeriesMomentum via nautilus_trader backtest.
Computes metrics matching TITAN's ValidationHarness output."""

import math
import statistics
from decimal import Decimal

import pandas as pd
import numpy as np

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import StrategyConfig, LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import TraderId, Venue, InstrumentId
from nautilus_trader.model.objects import Money, Price, Quantity
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.test_kit.providers import TestInstrumentProvider

INITIAL_CAPITAL = 100_000.0


class MomentumConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type_str: str
    trade_size: Decimal = Decimal(10)
    lookback: int = 20


class MomentumStrategy(Strategy):
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.prices: list[float] = []
        self.events: list[dict] = []

    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Instrument not found: {self.config.instrument_id}")
            self.stop()
            return
        bt = BarType.from_str(self.config.bar_type_str)
        self.subscribe_bars(bt)

    def on_bar(self, bar: Bar):
        close = float(bar.close.as_double())
        self.prices.append(close)
        if len(self.prices) < self.config.lookback + 1:
            self.events.append({"ts": bar.ts_init, "close": close, "signal": None})
            return
        ret = (self.prices[-1] - self.prices[-(self.config.lookback + 1)]) / self.prices[-(self.config.lookback + 1)]
        flat = self.portfolio.is_flat(self.config.instrument_id)
        if ret > 0 and flat:
            self.submit_order(self.order_factory.market(
                instrument_id=self.config.instrument_id, order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
                time_in_force=TimeInForce.GTC,
            ))
            self.events.append({"ts": bar.ts_init, "close": close, "signal": "BUY"})
        elif ret < 0 and not flat:
            self.close_all_positions(self.config.instrument_id)
            self.events.append({"ts": bar.ts_init, "close": close, "signal": "SELL"})
        else:
            self.events.append({"ts": bar.ts_init, "close": close, "signal": None})

    def on_stop(self):
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)


def to_price(v) -> Price:
    return Price.from_str(f"{float(v):.2f}")

def load_bars(csv_path: str, bar_type_str: str) -> list[Bar]:
    df = pd.read_csv(csv_path, parse_dates=["date"], dtype={c: float for c in "ohlc"}).sort_values("date")
    bt = BarType.from_str(bar_type_str)
    return [
        Bar(bar_type=bt, open=to_price(r["open"]), high=to_price(r["high"]),
            low=to_price(r["low"]), close=to_price(r["close"]),
            volume=Quantity.from_int(int(r["volume"])),
            ts_event=int(pd.Timestamp(r["date"]).value),
            ts_init=int(pd.Timestamp(r["date"]).value))
        for _, r in df.iterrows()
    ]


def main():
    csv_path = "tests/fixtures/market/real_spy_2020_2024.csv"
    bar_type_str = "SPY.SIM-1-DAY-LAST-EXTERNAL"

    bars = load_bars(csv_path, bar_type_str)
    split = pd.Timestamp("2023-01-01")
    test = [b for b in bars if pd.Timestamp(b.ts_init) >= split]
    dates = [pd.Timestamp(b.ts_init) for b in test]
    closes = [float(b.close.as_double()) for b in test]
    print(f"Test bars: {len(test)} | {dates[0].date()} to {dates[-1].date()}")

    config = BacktestEngineConfig(trader_id=TraderId("TITAN-001"), logging=LoggingConfig(log_level="ERROR"))
    engine = BacktestEngine(config=config)
    SIM = Venue("SIM")

    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.CASH,
                     base_currency=USD, starting_balances=[Money(INITIAL_CAPITAL, USD)],
                     fill_model=FillModel(prob_fill_on_limit=0.0, prob_slippage=0.0))

    spy = TestInstrumentProvider.equity(symbol="SPY", venue="SIM")
    engine.add_instrument(spy)
    engine.add_data(test)

    strat = MomentumStrategy(MomentumConfig(
        instrument_id=spy.id, bar_type_str=bar_type_str,
        trade_size=Decimal(10), lookback=20))
    engine.add_strategy(strategy=strat)
    engine.run()

    # ---- Build equity curve from events ----
    equity_curve = [INITIAL_CAPITAL]
    position = 0
    cash = INITIAL_CAPITAL
    trades = []
    buy_price = 0.0

    for e in strat.events:
        close = e["close"]
        sig = e["signal"]
        if sig == "BUY":
            cost = 10 * close
            if cost <= cash:
                cash -= cost
                position = 10
                buy_price = close
                trades.append({"side": "buy", "price": close, "ts": e["ts"]})
        elif sig == "SELL" and position > 0:
            proceeds = position * close
            pnl = proceeds - (position * buy_price)
            cash += proceeds
            trades[-1]["pnl"] = pnl
            trades[-1]["exit"] = close
            position = 0
        equity_curve.append(cash + position * close)

    final_equity = equity_curve[-1]
    total_return_pct = (final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    # ---- Compute metrics matching TITAN ----
    eq_arr = np.array(equity_curve)
    daily_returns = np.diff(eq_arr) / eq_arr[:-1]
    sharpe = 0.0
    if len(daily_returns) > 0 and np.std(daily_returns, ddof=1) > 0:
        sharpe = np.mean(daily_returns) / np.std(daily_returns, ddof=1) * math.sqrt(252)

    # Max drawdown
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak
    max_dd_pct = float(np.min(dd)) * 100

    # Win rate from round-trip trades
    all_trades = [t for t in trades if isinstance(t, dict) and "pnl" in t]
    wins = sum(1 for t in all_trades if t["pnl"] > 0)
    win_rate = wins / len(all_trades) * 100 if all_trades else 0

    # CAGR
    n_years = len(equity_curve) / 252
    cagr = (pow(final_equity / INITIAL_CAPITAL, 1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Profit factor
    gross_profit = sum(t["pnl"] for t in all_trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in all_trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Volatility (annualized)
    vol_annual = np.std(daily_returns, ddof=1) * math.sqrt(252) * 100 if len(daily_returns) > 0 else 0

    # Calmar
    calmar = (final_equity / INITIAL_CAPITAL - 1) * 100 / abs(max_dd_pct) if max_dd_pct != 0 else 0

    # Time in market
    position_dates = [pd.Timestamp(e["ts"]) for e in strat.events if e["signal"] == "SELL"]
    first_buy = next((pd.Timestamp(e["ts"]) for e in strat.events if e["signal"] == "BUY"), None)
    last_sell = next((pd.Timestamp(e["ts"]) for e in reversed(strat.events) if e["signal"] == "SELL"), None)
    time_in_market_pct = 0.0

    # Turnover
    total_turnover = sum(abs(t.get("pnl", 0)) for t in all_trades) / INITIAL_CAPITAL * 100

    print(f"\n{'='*60}")
    print(f"  NautilusTrader Backtest — Momentum(20) on SPY (OOS 2023-2024)")
    print(f"{'='*60}")
    print(f"\n  {'Metric':<25} {'Nautilus':>12} {'TITAN':>12}  {'Match':>8}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*8}")
    def chk(a, b, tol):
        return "YES" if abs(a - b) < tol else f"NO(diff={abs(a-b):.2f})"
    print(f"  {'Total Return %':<25} {total_return_pct:>12.2f} {'1.27':>12}  {chk(total_return_pct, 1.27, 1.0):>20}")
    print(f"  {'CAGR %':<25} {cagr:>12.2f} {'0.64':>12}  {chk(cagr, 0.64, 0.5):>20}")
    print(f"  {'Sharpe Ratio':<25} {sharpe:>12.4f} {'1.2950':>12}  {chk(sharpe, 1.295, 0.5):>20}")
    print(f"  {'Max DD %':<25} {max_dd_pct:>12.2f} {'0.47':>12}  {chk(abs(max_dd_pct), 0.47, 0.5):>20}")
    print(f"  {'Win Rate %':<25} {win_rate:>12.1f} {'37.5':>12}  {chk(win_rate, 37.5, 10):>20}")
    print(f"  {'Total Trades':<25} {len(all_trades):>12} {'32':>12}  {'YES' if len(all_trades) == 32 else 'NO':>20}")
    print(f"  {'Profit Factor':<25} {profit_factor:>12.4f} {'N/A':>12}  {'-':>8}")
    print(f"  {'Volatility %':<25} {vol_annual:>12.2f} {'N/A':>12}  {'-':>8}")
    print(f"  {'Calmar Ratio':<25} {calmar:>12.4f} {'N/A':>12}  {'-':>8}")

    print(f"\n  --- Extended Metrics ---")
    print(f"  Final Equity: ${final_equity:,.2f}")
    print(f"  Total PnL: ${final_equity - INITIAL_CAPITAL:,.2f}")

    # Print individual trades
    print(f"\n  Trades ({len(all_trades)}):")
    for i, t in enumerate(all_trades):
        side = "BUY " if t["side"] == "buy" else "SELL"
        pnl_str = f"PnL=${t.get('pnl', 0):+.2f}" if "pnl" in t else ""
        print(f"    {i+1:>2}. {side} @ ${t['price']:.2f}  {pnl_str}")

    engine.dispose()


if __name__ == "__main__":
    main()
