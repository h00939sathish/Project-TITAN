#!/usr/bin/env python3
"""Run a single strategy backtest. Called as subprocess by nautilus_backtest_runner.py."""

import math
import os
import statistics
import sys
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

def to_price(v):
    return Price.from_str(f"{float(v):.2f}")

def load_bars(csv_path, bar_type_str):
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

def metrics(eq, eq_series, trades):
    r = (eq[-1] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    eq_a = np.array(eq)
    dr = np.diff(eq_a) / eq_a[:-1]
    valid = dr[~np.isnan(dr) & ~np.isinf(dr)]
    sd = np.std(valid, ddof=1)
    sharpe = (np.mean(valid) / sd * math.sqrt(252)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq_a)
    mdd = float(np.min((eq_a - peak) / peak)) * 100
    all_trades = [t for t in trades if "pnl" in t]
    wins = sum(1 for t in all_trades if t["pnl"] > 0)
    wr = wins / len(all_trades) * 100 if all_trades else 0
    nyears = len(eq) / 252
    cagr = (pow(eq[-1]/INITIAL_CAPITAL, 1/nyears) - 1) * 100 if nyears > 0 else 0
    gp = sum(t["pnl"] for t in all_trades if t["pnl"] > 0)
    gl = abs(sum(t["pnl"] for t in all_trades if t["pnl"] < 0))
    pf = gp / gl if gl > 0 else float("inf")
    va = sd * math.sqrt(252) * 100 if sd > 0 else 0
    ca = r / abs(mdd) if mdd != 0 else 0
    return {"return": r, "cagr": cagr, "sharpe": sharpe, "mdd": mdd,
            "win_rate": wr, "trades": len(all_trades), "profit_factor": pf,
            "vol": va, "calmar": ca}

# -- Strategy implementations --
class MomStrategy(Strategy):
    def __init__(self, c):
        super().__init__(c); self.prices = []; self.events = []
    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        bt = BarType.from_str(self.config.bar_type_str); self.subscribe_bars(bt)
    def on_bar(self, bar):
        c = float(bar.close.as_double()); self.prices.append(c)
        if len(self.prices) < self.config.lookback + 1:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None, "ret": None}); return
        ret = (self.prices[-1] - self.prices[-(self.config.lookback + 1)]) / self.prices[-(self.config.lookback + 1)]
        flat = self.portfolio.is_flat(self.config.instrument_id)
        if ret > 0 and flat:
            self.submit_order(self.order_factory.market(instrument_id=self.config.instrument_id, order_side=OrderSide.BUY, quantity=self.instrument.make_qty(self.config.trade_size), time_in_force=TimeInForce.GTC))
            self.events.append({"ts": bar.ts_init, "close": c, "signal": "BUY"})
        elif ret < 0 and not flat:
            self.close_all_positions(self.config.instrument_id)
            self.events.append({"ts": bar.ts_init, "close": c, "signal": "SELL"})
        else:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None})

class MaCrossStrategy(Strategy):
    def __init__(self, c):
        super().__init__(c); self.prices = []; self.events = []
    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        bt = BarType.from_str(self.config.bar_type_str); self.subscribe_bars(bt)
    def on_bar(self, bar):
        c = float(bar.close.as_double()); self.prices.append(c)
        if len(self.prices) < self.config.slow + 1:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None}); return
        fma = sum(self.prices[-self.config.fast:]) / self.config.fast
        sma = sum(self.prices[-self.config.slow:]) / self.config.slow
        pf = sum(self.prices[-(self.config.fast+1):-1]) / self.config.fast
        ps = sum(self.prices[-(self.config.slow+1):-1]) / self.config.slow
        flat = self.portfolio.is_flat(self.config.instrument_id)
        if pf <= ps and fma > sma and flat:
            self.submit_order(self.order_factory.market(instrument_id=self.config.instrument_id, order_side=OrderSide.BUY, quantity=self.instrument.make_qty(self.config.trade_size), time_in_force=TimeInForce.GTC))
            self.events.append({"ts": bar.ts_init, "close": c, "signal": "BUY"})
        elif pf >= ps and fma < sma and not flat:
            self.close_all_positions(self.config.instrument_id)
            self.events.append({"ts": bar.ts_init, "close": c, "signal": "SELL"})
        else:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None})

class DualMaStrategy(Strategy):
    def __init__(self, c):
        super().__init__(c); self.prices = []; self.events = []; self._position = 0
    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        bt = BarType.from_str(self.config.bar_type_str); self.subscribe_bars(bt)
    def on_bar(self, bar):
        c = float(bar.close.as_double()); self.prices.append(c)
        if len(self.prices) < self.config.slow:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None}); return
        fma = sum(self.prices[-self.config.fast:]) / self.config.fast
        sma = sum(self.prices[-self.config.slow:]) / self.config.slow
        want_long = fma > sma
        if want_long and self._position != 1:
            if self._position == -1:
                self.close_all_positions(self.config.instrument_id)
            self.submit_order(self.order_factory.market(instrument_id=self.config.instrument_id, order_side=OrderSide.BUY, quantity=self.instrument.make_qty(self.config.trade_size), time_in_force=TimeInForce.GTC))
            self._position = 1; self.events.append({"ts": bar.ts_init, "close": c, "signal": "BUY"})
        elif not want_long and self._position != -1:
            if self._position == 1:
                self.close_all_positions(self.config.instrument_id)
                self.events.append({"ts": bar.ts_init, "close": c, "signal": "SELL"})
            self._position = -1
        else:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None})

class MrStrategy(Strategy):
    def __init__(self, c):
        super().__init__(c); self.prices = []; self.events = []; self._in_pos = False
    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        bt = BarType.from_str(self.config.bar_type_str); self.subscribe_bars(bt)
    def on_bar(self, bar):
        c = float(bar.close.as_double()); self.prices.append(c)
        if len(self.prices) < self.config.window + 1:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None}); return
        recent = self.prices[-self.config.window:]
        mn = statistics.mean(recent); sd = statistics.stdev(recent) if len(recent) > 1 else 1.0
        z = (c - mn) / max(sd, 1e-10); flat = self.portfolio.is_flat(self.config.instrument_id)
        if not self._in_pos and z < self.config.entry_z and flat:
            self.submit_order(self.order_factory.market(instrument_id=self.config.instrument_id, order_side=OrderSide.BUY, quantity=self.instrument.make_qty(self.config.trade_size), time_in_force=TimeInForce.GTC))
            self._in_pos = True; self.events.append({"ts": bar.ts_init, "close": c, "signal": "BUY"})
        elif self._in_pos and z > self.config.exit_z:
            self.close_all_positions(self.config.instrument_id)
            self._in_pos = False; self.events.append({"ts": bar.ts_init, "close": c, "signal": "SELL"})
        else:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None})

class VolStrategy(Strategy):
    def __init__(self, c):
        super().__init__(c); self.closes = []; self.events = []; self._in_pos = False
    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        bt = BarType.from_str(self.config.bar_type_str); self.subscribe_bars(bt)
    def on_bar(self, bar):
        c = float(bar.close.as_double()); self.closes.append(c)
        if len(self.closes) < self.config.median_window + 1:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None}); return
        rets = [(self.closes[i] - self.closes[i-1]) / self.closes[i-1] for i in range(-self.config.vol_window, 0)]
        vol = statistics.stdev(rets) if len(rets) > 1 else 0.0
        vols = []
        for i in range(-self.config.median_window, 0):
            start = i - self.config.vol_window
            if start < -len(self.closes): continue
            seg = self.closes[start:i]
            if len(seg) < 3: continue
            sr = [(seg[j] - seg[j-1]) / seg[j-1] for j in range(1, len(seg))]
            vols.append(statistics.stdev(sr))
        mv = statistics.median(vols) if vols else vol; thresh = mv * self.config.vol_multiple
        flat = self.portfolio.is_flat(self.config.instrument_id)
        if not self._in_pos and vol < thresh and flat:
            self.submit_order(self.order_factory.market(instrument_id=self.config.instrument_id, order_side=OrderSide.BUY, quantity=self.instrument.make_qty(self.config.trade_size), time_in_force=TimeInForce.GTC))
            self._in_pos = True; self.events.append({"ts": bar.ts_init, "close": c, "signal": "BUY"})
        elif self._in_pos and vol > thresh:
            self.close_all_positions(self.config.instrument_id)
            self._in_pos = False; self.events.append({"ts": bar.ts_init, "close": c, "signal": "SELL"})
        else:
            self.events.append({"ts": bar.ts_init, "close": c, "signal": None})

STRATEGIES = {
    "Momentum(20)": (MomStrategy, {"lookback": 20}),
    "MA Cross(5,20)": (MaCrossStrategy, {"fast": 5, "slow": 20}),
    "Dual MA(5,20)": (DualMaStrategy, {"fast": 5, "slow": 20}),
    "MeanRev(20,-2.0,-0.5)": (MrStrategy, {"window": 20, "entry_z": -2.0, "exit_z": -0.5}),
    "VolRegime(20,60,1.0)": (VolStrategy, {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0}),
}

# Config classes
from nautilus_trader.config import StrategyConfig, PositiveInt

class MomConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId; bar_type_str: str; trade_size: Decimal = Decimal(10); lookback: int = 20
class MaConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId; bar_type_str: str; trade_size: Decimal = Decimal(10); fast: int = 5; slow: int = 20
class DualConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId; bar_type_str: str; trade_size: Decimal = Decimal(10); fast: int = 5; slow: int = 20
class MrConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId; bar_type_str: str; trade_size: Decimal = Decimal(10); window: int = 20; entry_z: float = -2.0; exit_z: float = -0.5
class VolConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId; bar_type_str: str; trade_size: Decimal = Decimal(10); vol_window: int = 20; median_window: int = 60; vol_multiple: float = 1.0

CONFIGS = {
    "Momentum(20)": MomConfig,
    "MA Cross(5,20)": MaConfig,
    "Dual MA(5,20)": DualConfig,
    "MeanRev(20,-2.0,-0.5)": MrConfig,
    "VolRegime(20,60,1.0)": VolConfig,
}

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Momentum(20)"
    csv_path = sys.argv[2] if len(sys.argv) > 2 else "tests/fixtures/market/real_spy_2020_2024.csv"

    sc, kw = STRATEGIES[name]
    cc = CONFIGS[name]

    all_bars = load_bars(csv_path, "SPY.SIM-1-DAY-LAST-EXTERNAL")
    split = pd.Timestamp("2023-01-01")
    split_ns = int(split.value)
    test_bars = [b for b in all_bars if pd.Timestamp(b.ts_init) >= split]

    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId("TITAN-001"), logging=LoggingConfig(log_level="ERROR")))
    SIM = Venue("SIM")
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.CASH,
                     base_currency=USD, starting_balances=[Money(INITIAL_CAPITAL, USD)],
                     fill_model=FillModel(prob_fill_on_limit=0.0, prob_slippage=0.0))
    spy = TestInstrumentProvider.equity(symbol="SPY", venue="SIM")
    engine.add_instrument(spy)
    engine.add_data(all_bars)

    strat = sc(cc(instrument_id=spy.id, bar_type_str="SPY.SIM-1-DAY-LAST-EXTERNAL",
                  trade_size=Decimal(10), **kw))
    engine.add_strategy(strategy=strat)
    engine.run()

    position = 0; cash = INITIAL_CAPITAL; buy_price = 0.0; trades = []
    eq = [INITIAL_CAPITAL]
    pos = 0; csh = INITIAL_CAPITAL; bp = 0.0
    for e in strat.events:
        if e["ts"] < split_ns:
            continue  # skip warmup entirely
        c = e["close"]; s = e.get("signal")
        if s == "BUY" and pos == 0:
            cost = 10 * c
            if cost <= csh:
                csh -= cost; pos = 10; bp = c
                trades.append({"side": "buy", "price": c})
        elif s == "SELL" and pos > 0:
            pnl = pos * (c - bp)
            csh += pos * c
            trades[-1]["pnl"] = pnl
            pos = 0
        eq.append(csh + pos * c)

    m = metrics(eq, None, trades)
    m["name"] = name
    print(f"RESULT|{name}|{m['return']:.4f}|{m['cagr']:.4f}|{m['sharpe']:.4f}|{m['mdd']:.4f}|{m['win_rate']:.2f}|{m['trades']}|{m['profit_factor']:.4f}|{m['vol']:.4f}|{m['calmar']:.4f}")

    engine.dispose()

if __name__ == "__main__":
    main()
