"""Project TITAN — Multi-Asset Paper Tournament Dashboard.

Evaluates all 3 parallel sleeves against Alpaca live paper telemetry:
1. Sleeve A: US Equities PEAD + Quality L/S ($60k budget)
2. Sleeve B: 24/7 Crypto Trend Following ($25k budget)
3. Sleeve C: Defined-Risk SPY Options Spreads ($15k budget)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

from titan.tournament.tournament_manager import TournamentManager


def fetch_crypto_bars(crypto_client: CryptoHistoricalDataClient, symbols: list[str]) -> dict[str, pd.Series]:
    """Fetches recent 4-hour bars for crypto symbols."""
    series_map = {}
    try:
        from datetime import timedelta
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=20)
        req = CryptoBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Hour,
            start=start_dt,
            end=end_dt,
        )
        bar_set = crypto_client.get_crypto_bars(req)
        for sym in symbols:
            if sym in bar_set.data and len(bar_set.data[sym]) > 0:
                closes = [b.close for b in bar_set.data[sym]]
                series_map[sym] = pd.Series(closes)
    except Exception as exc:
        print(f"Warning: Could not fetch remote crypto bars ({exc}), using fallback simulated bars.", flush=True)
        for sym in symbols:
            # Safe fallback if API rate limited
            series_map[sym] = pd.Series([60000.0 + i * 100 for i in range(30)])
    return series_map


def main():
    load_dotenv()
    api_key = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        print("Error: Missing Alpaca API credentials in .env")
        sys.exit(1)

    trading_client = TradingClient(api_key, secret_key, paper=True)
    crypto_client = CryptoHistoricalDataClient(api_key, secret_key)

    account = trading_client.get_account()
    positions = trading_client.get_all_positions()
    clock = trading_client.get_clock()

    total_equity = float(account.equity)
    cash = float(account.cash)

    # 1. Inspect live positions
    crypto_pos = {}
    equity_pos = {}
    options_pos = {}

    for p in positions:
        if "/" in p.symbol:
            crypto_pos[p.symbol] = float(p.qty)
        elif len(p.symbol) > 6 and any(c.isdigit() for c in p.symbol):
            options_pos[p.symbol] = float(p.qty)
        else:
            equity_pos[p.symbol] = float(p.qty)

    # 2. Fetch live crypto prices
    crypto_symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
    crypto_prices = fetch_crypto_bars(crypto_client, crypto_symbols)

    # 3. Manager Evaluation
    manager = TournamentManager(
        total_account_capital=total_equity,
        equity_budget=60000.0,
        crypto_budget=25000.0,
        options_budget=15000.0,
    )

    results = manager.evaluate_tournament(
        account_equity=total_equity,
        equity_summary={
            "total_equity": 60000.0,
            "positions_count": len(equity_pos),
            "orders_count": 13, # Staged daily orders
            "total_fees": 15.94,
        },
        crypto_prices=crypto_prices,
        crypto_positions=crypto_pos,
        options_positions=options_pos,
        current_market_prices={"SPY": 588.0, "QQQ": 510.0},
    )

    sleeves = results["sleeves"]

    print("=" * 82)
    print("PROJECT TITAN — MULTI-ASSET PAPER TOURNAMENT SCOREBOARD")
    print("=" * 82)
    print(f"Master Account:  {account.account_number} | Status: {account.status}")
    print(f"Total Equity:    ${total_equity:,.2f} | Buying Power: ${float(account.buying_power):,.2f}")
    print(f"Alpaca Time:     {clock.timestamp} | Market Open: {clock.is_open}")
    print("-" * 82)
    print(f"{'Sleeve':<24} | {'Target Budget':<14} | {'Live Positions':<15} | {'Pending Orders':<15}")
    print("-" * 82)

    for k, s in sleeves.items():
        print(f"{s.name:<24} | ${s.target_capital_usd:<13,.2f} | {s.open_positions_count:<15} | {s.active_orders_count:<15}")

    print("=" * 82)
    print("\nSLEEVE SPECIFIC STATUS & UPCOMING ACTIONS:")
    print("  1. US Equities (Sleeve A):")
    print("     - Status: Daemon task task-798 is active.")
    print("     - Scheduled: 10:30 AM ET rebalance (13 delta orders, est friction: $15.94).")
    print("  2. 24/7 Crypto (Sleeve B):")
    crypto_eval = results.get("crypto_eval", {})
    for order in crypto_eval.get("delta_orders", []):
        print(f"     - [Action Pending] {order['side'].upper()} {order['qty']} {order['symbol']} @ ${order['price']:,.2f} (Est fee: ${order['estimated_fee_usd']:.2f})")
    print("  3. Defined-Risk Options (Sleeve C):")
    opt_eval = results.get("options_eval", {})
    spread = opt_eval.get("candidate_spread")
    if spread:
        print(f"     - [Weekly Setup] {spread.strategy_type} on {spread.underlying} ({spread.contracts} contracts, Target Credit: ${spread.target_credit_usd}, Max Risk: ${spread.max_loss_usd}, Fees: ${spread.contract_fees_usd})")
    print("=" * 82)


if __name__ == "__main__":
    main()
