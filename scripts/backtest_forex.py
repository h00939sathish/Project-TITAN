"""Forex backtest smoke test — runs a trivial strategy on EUR/USD fixture data.

Usage:
    python scripts/backtest_forex.py
    python scripts/backtest_forex.py --live-data
"""

import argparse
from datetime import datetime, timezone

from titan._core import Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.data.forex_pairs import forex_instrument
from titan.execution import PaperConfig, PaperTradingEngine
from titan.execution.backtest_adapter import BacktestAdapter


def run_forex_backtest() -> dict:
    inst = forex_instrument("EURUSD")
    assert inst is not None, "EURUSD instrument not found"

    # Load fixture bars
    import csv
    bars: list[dict] = []
    with open("tests/data/fixtures/eurusd_2026.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["timestamp"] = row["date"]
            for k in ("open", "high", "low", "close"):
                row[k] = float(row[k])
            bars.append(row)

    risk = RiskConfig(
        list({"EURUSD"}),  # instrument eligibility
        Money("100000", "USD"),
        100000,   # max_order_quantity
        100000,   # max_position_size
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,   # clock_skew_tolerance_ms (60s for safety)
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        ),
        currency="USD",
        starting_capital="100000",
        account_id="forex-bt-1",
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

        # Trivial strategy: buy if price > previous bar close (simple momentum)
        close = float(bar["close"])
        # Just buy on first bar and hold
        if trades == 0:
            intent = TradeIntent(
                strategy_id="forex-smoke",
                strategy_package_digest="v1",
                account_id="forex-bt-1",
                instrument_id="EURUSD",
                side="BUY",
                quantity="1000",
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

        engine._last_prices["EURUSD"] = str(close)
        try:
            engine.portfolio.update_market_price("EURUSD", str(close))
        except Exception:
            pass

    # Sell to close
    if trades > 0:
        intent = TradeIntent(
            strategy_id="forex-smoke",
            strategy_package_digest="v1",
            account_id="forex-bt-1",
            instrument_id="EURUSD",
            side="SELL",
            quantity="1000",
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
    pos = engine.portfolio.get_position("EURUSD")
    return {
        "trades": trades,
        "rejected": rejected,
        "final_cash": str(cash.amount),
        "final_position": pos.quantity if pos else 0,
    }


def run_live_backtest() -> dict:
    from titan.data.polygon_feed import fetch_daily_bars
    bars = fetch_daily_bars("EURUSD", 30)
    if not bars:
        return {"trades": 0, "rejected": 0, "final_cash": "0", "final_position": 0}

    inst = forex_instrument("EURUSD")
    assert inst is not None, "EURUSD instrument not found"

    risk = RiskConfig(
        list({"EURUSD"}),
        Money("100000", "USD"),
        100000, 100000,
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        ),
        currency="USD",
        starting_capital="100000",
        account_id="forex-bt-1",
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
                strategy_id="forex-smoke",
                strategy_package_digest="v1",
                account_id="forex-bt-1",
                instrument_id="EURUSD",
                side="BUY",
                quantity="1000",
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

        engine._last_prices["EURUSD"] = str(close)
        try:
            engine.portfolio.update_market_price("EURUSD", str(close))
        except Exception:
            pass

    if trades > 0:
        intent = TradeIntent(
            strategy_id="forex-smoke",
            strategy_package_digest="v1",
            account_id="forex-bt-1",
            instrument_id="EURUSD",
            side="SELL",
            quantity="1000",
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
    pos = engine.portfolio.get_position("EURUSD")
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
        result = run_forex_backtest()
    print(f"Trades executed: {result['trades']}")
    print(f"Rejected:        {result['rejected']}")
    print(f"Final cash:      ${result['final_cash']}")
    print(f"Final position:  {result['final_position']}")
    if not args.live_data:
        assert result["trades"] == 2, f"Expected 2 trades (buy + sell), got {result['trades']}"
        assert result["rejected"] == 0, f"Expected 0 rejections, got {result['rejected']}"
        assert result["final_position"] == 0, f"Expected flat position, got {result['final_position']}"
    print("\nPASS — Forex backtest smoke test passed")
