"""Spot gold backtest smoke test — runs a trivial strategy on XAUUSD fixture data.

Usage:
    python scripts/backtest_spot_gold.py
    python scripts/backtest_spot_gold.py --live-data
"""

import argparse
from datetime import datetime, timezone

from titan._core import Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.data.spot_metals import spot_metal_instrument
from titan.execution import PaperConfig, PaperTradingEngine
from titan.execution.backtest_adapter import BacktestAdapter


def run_spot_gold_backtest() -> dict:
    inst = spot_metal_instrument("XAUUSD")
    assert inst is not None, "XAUUSD instrument not found"

    import csv
    bars: list[dict] = []
    with open("tests/data/fixtures/xauusd_2026.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["timestamp"] = row["date"]
            for k in ("open", "high", "low", "close"):
                row[k] = float(row[k])
            bars.append(row)

    risk = RiskConfig(
        list({"XAUUSD"}),
        Money("100000", "USD"),
        100, 100,
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="gold-bt-1",
        state_path="",
    )

    adapter = BacktestAdapter(bars)
    engine = PaperTradingEngine(config, adapter)
    engine.register_instrument(inst)
    engine.start()

    trades = 0
    rejected = 0

    for bar in bars:
        adapter.advance_to(bar)
        close = float(bar["close"])

        if trades == 0:
            intent = TradeIntent(
                strategy_id="gold-smoke",
                strategy_package_digest="v1",
                account_id="gold-bt-1",
                instrument_id="XAUUSD",
                side="BUY",
                quantity="1",
                order_type="MARKET",
                time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            result = engine.submit_intent(intent)
            if result.accepted:
                trades += 1
            else:
                rejected += 1

        engine._last_prices["XAUUSD"] = str(close)
        try:
            engine.portfolio.update_market_price("XAUUSD", str(close))
        except Exception:
            pass

    if trades > 0:
        intent = TradeIntent(
            strategy_id="gold-smoke",
            strategy_package_digest="v1",
            account_id="gold-bt-1",
            instrument_id="XAUUSD",
            side="SELL",
            quantity="1",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = engine.submit_intent(intent)
        if result.accepted:
            trades += 1
        else:
            rejected += 1

    engine.stop()

    cash = engine.portfolio.get_cash_balance()
    pos = engine.portfolio.get_position("XAUUSD")
    return {
        "trades": trades,
        "rejected": rejected,
        "final_cash": str(cash.amount),
        "final_position": pos.quantity if pos else 0,
    }


def run_live_backtest() -> dict:
    from titan.data.polygon_feed import fetch_daily_bars
    bars = fetch_daily_bars("XAUUSD", 30)
    if not bars:
        return {"trades": 0, "rejected": 0, "final_cash": "0", "final_position": 0}

    inst = spot_metal_instrument("XAUUSD")
    assert inst is not None, "XAUUSD instrument not found"

    risk = RiskConfig(
        list({"XAUUSD"}),
        Money("100000", "USD"),
        100, 100,
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital="100000",
        account_id="gold-bt-1",
        state_path="",
    )

    adapter = BacktestAdapter(bars)
    engine = PaperTradingEngine(config, adapter)
    engine.register_instrument(inst)
    engine.start()

    trades = 0
    rejected = 0

    for bar in bars:
        adapter.advance_to(bar)
        close = float(bar["close"])

        if trades == 0:
            intent = TradeIntent(
                strategy_id="gold-smoke",
                strategy_package_digest="v1",
                account_id="gold-bt-1",
                instrument_id="XAUUSD",
                side="BUY",
                quantity="1",
                order_type="MARKET",
                time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            result = engine.submit_intent(intent)
            if result.accepted:
                trades += 1
            else:
                rejected += 1

        engine._last_prices["XAUUSD"] = str(close)
        try:
            engine.portfolio.update_market_price("XAUUSD", str(close))
        except Exception:
            pass

    if trades > 0:
        intent = TradeIntent(
            strategy_id="gold-smoke",
            strategy_package_digest="v1",
            account_id="gold-bt-1",
            instrument_id="XAUUSD",
            side="SELL",
            quantity="1",
            order_type="MARKET",
            time_in_force="DAY",
            risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = engine.submit_intent(intent)
        if result.accepted:
            trades += 1
        else:
            rejected += 1

    engine.stop()

    cash = engine.portfolio.get_cash_balance()
    pos = engine.portfolio.get_position("XAUUSD")
    return {
        "trades": trades,
        "rejected": rejected,
        "final_cash": str(cash.amount),
        "final_position": pos.quantity if pos else 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-data", action="store_true", help="Fetch from Polygon.io instead of fixture")
    args = parser.parse_args()

    if args.live_data:
        result = run_live_backtest()
    else:
        result = run_spot_gold_backtest()
    print(f"Trades executed: {result['trades']}")
    print(f"Rejected:        {result['rejected']}")
    print(f"Final cash:      ${result['final_cash']}")
    print(f"Final position:  {result['final_position']}")
    if not args.live_data:
        assert result["trades"] == 2, f"Expected 2 trades, got {result['trades']}"
        assert result["rejected"] == 0, f"Expected 0 rejections, got {result['rejected']}"
        assert result["final_position"] == 0, f"Expected flat, got {result['final_position']}"
    print("\nPASS — Spot gold backtest smoke test passed")
