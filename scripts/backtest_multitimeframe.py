"""Multi-timeframe backtest — mirrors ibkr_paper_session.py flow but with BacktestAdapter.

Architecture:
  CSV bars → MarketEvent → RuntimeEvaluator → MultiTimeframeRuntime
  → TradeProposal → TradeIntent → PaperTradingEngine.submit_intent() → BacktestAdapter.

Usage:
    python scripts/backtest_multitimeframe.py
    python scripts/backtest_multitimeframe.py --csv tests/fixtures/market/real_qqq_2020_2024.csv --risk-pct 5
    python scripts/backtest_multitimeframe.py --sweep
"""

import argparse
import csv
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import titan.strategies.registrations  # noqa: F401
from titan._core import ContractType, Instrument, InstrumentId as TitanInstrumentId, Money, RiskConfig, TradeIntent
from titan.execution.backtest_adapter import BacktestAdapter
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.runtime.events import MarketEvent, StrategyDefinition, TriggerSpec
from titan.runtime.evaluator import RuntimeEvaluator
from titan.strategies.multitimeframe_runtime import MultiTimeframeRuntime
from titan.strategies.registry import get_registry
from titan.strategies.shadow import ShadowDeployer, ShadowTrade
from titan.strategies.timeframes import Timeframe

log = logging.getLogger("titan.backtest")

INSTRUMENT_ID = os.getenv("BACKTEST_INSTRUMENT", "SPY.ARCA")
INSTRUMENT_SYMBOL = INSTRUMENT_ID.split(".")[0]

STRATEGY_IDS = [
    "time-series-momentum",
    "ma-crossover",
    "mean-reversion",
    "volatility-regime",
    "dual-ma",
]

STRATEGY_PARAMS = {
    "time-series-momentum": {"lookback": 20},
    "ma-crossover": {"fast": 5, "slow": 20},
    "mean-reversion": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
    "volatility-regime": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
    "dual-ma": {"fast": 5, "slow": 20},
}

ALL_TIMEFRAMES = [Timeframe.FIVE_MINUTES, Timeframe.FIFTEEN_MINUTES, Timeframe.ONE_HOUR, Timeframe.ONE_DAY]

DEFAULT_EQUITY = int(os.getenv("EQUITY", "100000"))
DEFAULT_RISK_PCT = float(os.getenv("RISK_PCT", "10.0"))
WATCHLIST_IDS: set[str] = set(
    sid.strip() for sid in os.getenv("WATCHLIST_IDS", "time-series-momentum,mean-reversion").split(",") if sid.strip()
)

SWEEP_GRID = {
    "time-series-momentum": [{"lookback": lb} for lb in (5, 10, 20, 50, 100)],
    "ma-crossover": [{"fast": f, "slow": s} for f in (2, 5, 10, 20) for s in (10, 20, 50, 100) if f < s],
    "mean-reversion": [{"window": w, "entry_z": -2.0, "exit_z": -0.5} for w in (10, 20, 30, 50)],
    "volatility-regime": [{"vol_window": vw, "median_window": mw, "vol_multiple": 1.0} for vw in (10, 20, 30) for mw in (30, 60, 90) if vw < mw],
    "dual-ma": [{"fast": f, "slow": s} for f in (2, 5, 10, 20) for s in (10, 20, 50, 100) if f < s],
}


def load_bars(path: str) -> list[dict]:
    bars: list[dict] = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["timestamp"] = row.get("date", row.get("timestamp", ""))
            for k in ("open", "high", "low", "close", "volume"):
                if k in row:
                    row[k] = float(row[k]) if k != "volume" else int(float(row[k]))
            bars.append(row)
    if not bars:
        raise ValueError(f"No data in {path}")
    return bars


def make_instrument() -> Instrument:
    sym, exch = INSTRUMENT_ID.split(".")
    return Instrument(TitanInstrumentId(sym, exch), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)


def bar_to_market_event(bar: dict, counter: int, timeframe: Timeframe = Timeframe.ONE_DAY) -> MarketEvent:
    ts = datetime.now(timezone.utc)
    return MarketEvent(
        message_id=f"bt-{counter}",
        causation_id=f"bt-bar-{counter}",
        correlation_id=f"corr-{counter}",
        occurred_at=ts,
        received_at=ts,
        schema_version=1,
        source="backtest",
        event_type="BarClosed",
        instrument_id=INSTRUMENT_ID,
        payload={
            "timeframe": timeframe.value,
            "close": float(bar["close"]),
            "open": float(bar.get("open", bar["close"])),
            "high": float(bar.get("high", bar["close"])),
            "low": float(bar.get("low", bar["close"])),
            "volume": int(bar.get("volume", 0)),
        },
        payload_digest="",
    )


def print_qualification_summary():
    reg = get_registry()
    qualified: dict[str, list[str]] = defaultdict(list)
    total_qf = 0
    for sid in STRATEGY_IDS:
        try:
            r = reg.get(sid)
            for tf, _ in r.qualified_variants:
                qualified[tf.value].append(sid)
                total_qf += 1
        except KeyError:
            pass

    print(f"\n========== TITAN Backtest ==========")
    print(f"  Instrument:    {INSTRUMENT_ID}")
    print(f"  Equity:        ${DEFAULT_EQUITY:,}")
    print(f"  Risk pct:      {DEFAULT_RISK_PCT}%")
    print(f"  Strategies:    {len(STRATEGY_IDS)} registered, {total_qf} qualified variants")
    for tf_name in ("1d", "1h", "15m", "5m"):
        strs = qualified.get(tf_name, [])
        label = {"1d": "Daily", "1h": "1 Hour", "15m": "15 Minute", "5m": "5 Minute"}.get(tf_name, tf_name)
        if strs:
            for s in sorted(strs):
                print(f"  {s:25s} [{label:10s}] QUALIFIED")
        else:
            print(f"  {'(none)':25s} [{label:10s}] BLOCKED")
    print("  ---")
    print("  [OK] Qualification DB Loaded")
    print("  [OK] Backtest Mode")
    print("  READY\n")


def run_once(bars: list[dict], risk_pct: float, strategy_params: dict[str, dict] | None = None,
             quiet: bool = False, data_timeframe: Timeframe = Timeframe.ONE_DAY) -> dict:
    params = strategy_params or STRATEGY_PARAMS

    risk_config = RiskConfig(
        [INSTRUMENT_ID],
        Money("50000", "USD"),
        1000, 100000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000, 100,
        max_correlated_exposure=1.0,
    )
    config = PaperConfig(
        risk_config=risk_config,
        currency="USD",
        starting_capital=str(DEFAULT_EQUITY),
        account_id="bt-mtf-1",
        state_path="",
    )

    adapter = BacktestAdapter(bars)
    engine = PaperTradingEngine(config, adapter)
    engine.register_instrument(make_instrument(), INSTRUMENT_ID)
    engine.start()

    shadow = ShadowDeployer()

    multirt = MultiTimeframeRuntime(risk_pct=risk_pct, watchlist_ids=WATCHLIST_IDS)
    evaluator = RuntimeEvaluator()

    for sid in STRATEGY_IDS:
        p = params[sid]
        for tf in ALL_TIMEFRAMES:
            evaluator.register(StrategyDefinition(
                strategy_id=sid,
                trigger=TriggerSpec(event_type="BarClosed", timeframe=tf),
                params=p,
            ))
            multirt.register(StrategyDefinition(
                strategy_id=sid,
                trigger=TriggerSpec(event_type="BarClosed", timeframe=tf),
                params=p,
            ))

    evaluator.set_producer(multirt)

    warmup_prices = [float(b["close"]) for b in bars[:20]]
    multirt.warmup(INSTRUMENT_ID, data_timeframe, warmup_prices)

    counts: dict[str, int] = {"bars": 0, "proposals": 0, "submitted": 0, "accepted": 0, "rejected": 0}
    strategy_trades: dict[str, int] = defaultdict(int)

    for i, bar in enumerate(bars):
        adapter.advance_to(bar)
        close = float(bar["close"])
        counts["bars"] += 1

        event = bar_to_market_event(bar, i, timeframe=data_timeframe)
        result = evaluator.on_market_event(event)
        proposals = result.proposals if result else []
        counts["proposals"] += len(proposals)

        for proposal in proposals:
            if proposal.producer_kind == "shadow":
                shadow.record(ShadowTrade(
                    strategy_id=proposal.strategy_id,
                    instrument_id=proposal.instrument_id,
                    side=proposal.side,
                    quantity=str(int(proposal.quantity)),
                    price=proposal.price,
                    timestamp=proposal.close_timestamp.isoformat() if proposal.close_timestamp else "",
                ))
                continue

            counts["submitted"] += 1
            intent = TradeIntent(
                strategy_id=proposal.strategy_id,
                strategy_package_digest="",
                account_id=config.account_id,
                instrument_id=proposal.instrument_id,
                side=proposal.side,
                quantity=str(int(proposal.quantity)),
                order_type="MARKET",
                time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                price=str(proposal.price) if proposal.price else None,
            certificate_ref="backtest-cert",
            )
            order_result = engine.submit_intent(intent, correlation_id=event.correlation_id)
            if order_result.accepted:
                counts["accepted"] += 1
                strategy_trades[proposal.strategy_id] += 1
            else:
                counts["rejected"] += 1

        engine.update_price(INSTRUMENT_ID, close)

    engine.stop()

    final_cash = engine.portfolio.get_cash_balance()
    pos = engine.portfolio.get_position(INSTRUMENT_ID)
    pos_value = abs(pos.quantity) * float(bars[-1]["close"]) if pos else 0
    final_value = float(final_cash.amount) + pos_value
    total_return = (final_value - DEFAULT_EQUITY) / DEFAULT_EQUITY * 100.0

    if not quiet:
        print(f"  Data timeframe:   {data_timeframe.value}")
        print(f"  Risk pct:         {risk_pct}%")
        print(f"  Bars:             {counts['bars']}")
        print(f"  Proposals:        {counts['proposals']}")
        print(f"  Orders accepted:  {counts['accepted']}")
        print(f"  Orders rejected:  {counts['rejected']}")
        print(f"  Final cash:       ${float(final_cash.amount):.2f}")
        print(f"  Final position:   {pos.quantity if pos else 0} shares")
        print(f"  Total return:     {total_return:+.2f}%")
        print(f"  Buy & Hold:       {((float(bars[-1]['close']) - float(bars[0]['close'])) / float(bars[0]['close'])) * 100:+.2f}%")
        print(f"  --- per strategy ---")
        for sid, n in sorted(strategy_trades.items()):
            print(f"    {sid}: {n} trades")
        print(f"  --- shadow (WATCHLIST) ---")
        for sid in sorted(WATCHLIST_IDS):
            trades = shadow.trades_for(sid)
            if trades:
                print(f"    {sid}: {len(trades)} shadow trades (last: {trades[-1].side} {trades[-1].quantity})")

    return {
        "bars": counts["bars"],
        "proposals": counts["proposals"],
        "submitted": counts["submitted"],
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "final_cash": float(final_cash.amount),
        "final_position": pos.quantity if pos else 0,
        "total_return_pct": round(total_return, 2),
        "strategy_trades": dict(strategy_trades),
    }


def run_sweep(bars: list[dict], risk_pct: float):
    print(f"\n=== Parameter Sweep ({len(bars)} bars, risk_pct={risk_pct}%) ===\n")
    for sid, grid in SWEEP_GRID.items():
        results: list[tuple[dict, dict]] = []
        for params in grid:
            sp = STRATEGY_PARAMS.copy()
            sp[sid] = params
            r = run_once(bars, risk_pct, strategy_params=sp, quiet=True, data_timeframe=Timeframe.ONE_DAY)
            results.append((params, r))
        results.sort(key=lambda x: x[1]["total_return_pct"], reverse=True)
        qualified_only = [r for r in results if _is_qualified(sid, r[0])]
        display = qualified_only[:5] if qualified_only else results[:5]
        print(f"  {sid} — top {len(display)} of {len(results)}:")
        for params, r in display:
            desc = ",".join(f"{k}={v}" for k, v in params.items())
            q = " [Q]" if _is_qualified(sid, params) else " [X]"
            print(f"    {desc:45s}  return={r['total_return_pct']:+.2f}%  trades={r['accepted']}{q}")
        print()


def _is_qualified(sid: str, params: dict) -> bool:
    import json
    reg = get_registry()
    try:
        r = reg.get(sid)
    except KeyError:
        return False
    return (Timeframe.ONE_DAY, json.dumps(params, sort_keys=True)) in r.qualified_variants


def main():
    parser = argparse.ArgumentParser(description="Multi-timeframe backtest")
    parser.add_argument("--csv", default="tests/fixtures/market/real_spy_2020_2024.csv",
                        help="Path to CSV bar data")
    parser.add_argument("--risk-pct", type=float, default=DEFAULT_RISK_PCT,
                        help=f"Risk percentage per trade (default: {DEFAULT_RISK_PCT})")
    parser.add_argument("--sweep", action="store_true",
                        help="Run parameter sweep (only qualified params produce trades)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stdout)

    bars = load_bars(args.csv)
    start = bars[0].get("date", bars[0].get("timestamp", "?"))
    end = bars[-1].get("date", bars[-1].get("timestamp", "?"))
    print(f"Loaded {len(bars)} bars ({start} to {end})")

    print_qualification_summary()

    if args.sweep:
        run_sweep(bars, args.risk_pct)
    else:
        print(f"=== Multi-Timeframe Backtest ===\n")
        run_once(bars, args.risk_pct)


if __name__ == "__main__":
    main()
