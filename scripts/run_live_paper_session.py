"""Project TITAN — Live Alpaca Paper Trading Session Driver.

Connects to the Alpaca Paper Trading account (PA33BCWZ2NX8), inspects live positions,
evaluates PEAD + Quality factor rankings, and executes/stages rebalance orders
under full compliance gate protection.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from dotenv import load_dotenv
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.trading.requests import LimitOrderRequest

from titan.backtest.alpaca_equity_costs import AlpacaEquityCostModel
from titan.data.equities_universe import EquitiesUniverseManifest, build_equities_universe
from titan.execution.alpaca_batch import AlpacaBatchDispatcher, BatchOrderIntent
from titan.operations.daily_rebalance import DailyRebalanceOrchestrator
from titan.research.equities_event_screen_009 import load_pit_earnings_events
from titan.risk.alpaca_compliance import AlpacaComplianceGate

MANIFEST_PATH = _REPO_ROOT / "research" / "equities" / "manifests" / "us_sp50_earnings_pit_v1.json"
EVENTS_PATH = _REPO_ROOT / "research" / "equities" / "data" / "us_sp50_earnings_events_v1.parquet"
CACHE_DIR = _REPO_ROOT / "research_data" / "intraday_5m"


class LiveAlpacaBrokerClient:
    """Wrapper around Alpaca TradingClient for order execution in paper mode."""

    def __init__(self, client: TradingClient):
        self.client = client
        self.dispatched_orders = []

    def place_order(self, intent: BatchOrderIntent):
        side = OrderSide.BUY if intent.side.lower() in ("buy", "buy_to_cover") else OrderSide.SELL
        req = LimitOrderRequest(
            symbol=intent.symbol,
            qty=intent.shares,
            side=side,
            time_in_force=TimeInForce.DAY,
            limit_price=float(intent.target_price),
        )
        order = self.client.submit_order(req)
        self.dispatched_orders.append(order)
        return order


def run_live_paper_rebalance(dry_run: bool = True):
    load_dotenv()
    api_key = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        raise ValueError("APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in .env")

    client = TradingClient(api_key, secret_key, paper=True)
    account = client.get_account()
    positions = client.get_all_positions()
    clock = client.get_clock()

    print("=" * 78)
    print("PROJECT TITAN — LIVE ALPACA PAPER SESSION")
    print("=" * 78)
    print(f"Account:         {account.account_number} ({account.status})")
    print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
    print(f"Equity:          ${float(account.equity):,.2f}")
    print(f"Cash:            ${float(account.cash):,.2f}")
    print(f"Buying Power:    ${float(account.buying_power):,.2f}")
    print(f"Current Time:    {clock.timestamp} (Market Open: {clock.is_open})")
    print(f"Mode:            {'DRY-RUN (Preflight Validation)' if dry_run else 'LIVE PAPER SUBMISSION'}")
    print("-" * 78)

    # Map current live positions
    current_positions = {p.symbol: int(p.qty) for p in positions}
    print(f"Current Holdings ({len(current_positions)} symbols):")
    for sym, qty in current_positions.items():
        print(f"  {sym:<6}: {qty:>4} shares")

    # Load factor price matrix
    manifest = EquitiesUniverseManifest.load(MANIFEST_PATH)
    events_df = load_pit_earnings_events(EVENTS_PATH)

    series_map = {}
    for sym in manifest.universe:
        p = CACHE_DIR / f"{sym}_5m.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        daily = df.groupby(df.index.tz_convert("America/New_York").date)["close"].last()
        daily.index = pd.to_datetime(daily.index)
        series_map[sym] = daily

    universe = build_equities_universe(series_map, manifest)
    prices_df = universe.prices
    current_prices = {sym: float(prices_df[sym].iloc[-1]) for sym in prices_df.columns}

    # Setup orchestrator
    gate = AlpacaComplianceGate()
    broker_adapter = LiveAlpacaBrokerClient(client) if not dry_run else None

    orchestrator = DailyRebalanceOrchestrator(
        compliance_gate=gate,
        broker_client=broker_adapter,
        pacing_delay_seconds=0.10,
    )

    total_equity = float(account.equity)
    print("\nEvaluating Compliance & Factor Engine...", flush=True)

    summary = orchestrator.execute_daily_cycle(
        prices_df=prices_df,
        current_positions=current_positions,
        current_prices=current_prices,
        account_equity=total_equity,
        events_df=events_df,
        etb_symbols=list(prices_df.columns),
        top_k=5,
        bottom_k=5,
    )

    print("-" * 78)
    print(f"Compliance Gate: {'APPROVED' if summary.compliance_approved else 'REJECTED'}")
    print(f"Operational Tier: Tier {summary.tier} (Equity: ${total_equity:,.2f})")
    print(f"Orders Computed:  {len(summary.dispatched_orders)} orders")

    cost_model = AlpacaEquityCostModel.standard_retail()
    est_friction = Decimal("0.00")

    print("\nPlanned Rebalance Orders:")
    for o in summary.dispatched_orders:
        cost = cost_model.calculate_cost(side=o["side"], shares=o["shares"], price=o["price"], is_etb=True)
        est_friction += cost.total_friction_usd
        print(f"  {o['side'].upper():<5} {o['shares']:>4} shs {o['symbol']:<5} @ ${o['price']:>7.2f} (Notional: ${o['notional']:>8.2f}) | Friction: ${cost.total_friction_usd:.4f} (Comm: $0.00)")

    print(f"\nTotal Estimated Batch Friction: ${est_friction:.2f} ($0 Commission, $0 ETB Borrow)")
    print("=" * 78)
    return summary


if __name__ == "__main__":
    dry_run = "--live" not in sys.argv
    run_live_paper_rebalance(dry_run=dry_run)
