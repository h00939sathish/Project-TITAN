#!/usr/bin/env python3
"""Paper trading CLI — start, trade, reconcile, stop.

Usage:
    python scripts/papertrade.py start              # authenticate + sync from broker
    python scripts/papertrade.py status [-r]        # show positions, balance, health
    python scripts/papertrade.py buy SYMBOL QTY [-r]  # place a market buy
    python scripts/papertrade.py sell SYMBOL QTY [-r] # place a market sell
    python scripts/papertrade.py reconcile [-r]     # compare portfolio vs broker
    python scripts/papertrade.py stop               # shut down

Flags:
    -r, --from-broker   Force re-sync from broker (skip state file)
"""

import os
import sys

from dotenv import load_dotenv
from titan._core import Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.execution import (
    AlpacaAdapter,
    EngineStatus,
    PaperConfig,
    PaperTradingEngine,
)

load_dotenv()


def _build_engine() -> PaperTradingEngine:
    api_key = os.environ.get("APCA_API_KEY_ID", "")
    api_secret = os.environ.get("APCA_API_SECRET_KEY", "")
    base_url = os.environ.get("APCA_API_BASE_URL", "")

    if not api_key or not api_secret:
        print("ERROR: APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in .env")
        sys.exit(1)

    instrument_list = os.environ.get("PAPER_INSTRUMENTS", "AAPL,SPY,QQQ,MSFT").split(",")
    max_notional = os.environ.get("PAPER_MAX_NOTIONAL", "50000")
    max_order_qty = os.environ.get("PAPER_MAX_ORDER_QTY", "1000")
    daily_loss_limit = os.environ.get("PAPER_DAILY_LOSS_LIMIT", "5000")
    starting_capital = os.environ.get("PAPER_STARTING_CAPITAL", "100000")
    account_id = os.environ.get("PAPER_ACCOUNT_ID", "paper-1")

    clock_skew = int(os.environ.get("PAPER_CLOCK_SKEW_TOLERANCE_MS", "100"))
    risk_config = RiskConfig(
        instrument_list,
        Money(max_notional, "USD"),
        int(max_order_qty),
        int(max_order_qty),
        Money(daily_loss_limit, "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        clock_skew,
    )

    config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        ),
        currency="USD",
        starting_capital=starting_capital,
        account_id=account_id,
    )

    adapter = AlpacaAdapter(
        api_key=api_key,
        secret_key=api_secret,
        base_url=base_url or None,
    )

    return PaperTradingEngine(config, adapter)


def _show_status(status: EngineStatus):
    print(f"Trading state: {status.trading_state}")
    print(f"Kill switch:  {status.kill_switch}")
    print(f"Cash:         {status.cash_balance}")
    print(f"Portfolio:    {status.portfolio_value}")

    if status.adapter_health:
        print(f"Adapter:      {'CONNECTED' if status.adapter_health.connected else 'DISCONNECTED'}")
        if status.adapter_health.degradation:
            for d in status.adapter_health.degradation:
                print(f"  Degraded:   {d}")
    else:
        print("Adapter:      UNKNOWN")

    if status.positions:
        print(f"Positions ({len(status.positions)}):")
        for p in status.positions:
            print(f"  {p.instrument_id}: {p.side} {p.quantity}")
    else:
        print("Positions:    none")

    if status.open_orders:
        print(f"Open orders:  {status.open_orders}")
    else:
        print("Open orders:  none")


def _has_flag(flag: str) -> bool:
    return flag in sys.argv


def _get_positional_args() -> list[str]:
    known = {"-r", "--from-broker"}
    return [a for a in sys.argv[2:] if a not in known]


def cmd_start():
    engine = _build_engine()
    session = engine.start(sync_from_broker=True)
    print(f"Session: {session.session_id} ({session.state.value})")
    _show_status(engine.status())
    print("\nReady to trade. Use: python scripts/papertrade.py buy|sell SYMBOL QTY")


def cmd_status():
    engine = _build_engine()
    sync = _has_flag("-r") or _has_flag("--from-broker")
    try:
        engine.start(sync_from_broker=sync)
    except Exception as e:
        print(f"WARNING: could not authenticate: {e}")
    _show_status(engine.status())


def cmd_buy(symbol: str, qty: str):
    engine = _build_engine()
    sync = _has_flag("-r") or _has_flag("--from-broker")
    engine.start(sync_from_broker=sync)
    intent = TradeIntent(
        "cli", "cli-pkg", engine.config.account_id,
        symbol.upper(), "BUY", qty, "MARKET", "DAY", "1.0",
    )
    result = engine.submit_intent(intent)
    if result.accepted:
        print(f"ORDER ACCEPTED: {result.broker_order_id}")
        if result.fills:
            for f in result.fills:
                print(f"  FILL: {f.quantity} x {f.instrument_id} @ {f.price}")
        if result.cash_balance:
            print(f"  Cash: {result.cash_balance}")
    else:
        print(f"ORDER REJECTED: {result.rejection_reason}")
    _show_status(engine.status())


def cmd_sell(symbol: str, qty: str):
    engine = _build_engine()
    sync = _has_flag("-r") or _has_flag("--from-broker")
    engine.start(sync_from_broker=sync)
    intent = TradeIntent(
        "cli", "cli-pkg", engine.config.account_id,
        symbol.upper(), "SELL", qty, "MARKET", "DAY", "1.0",
    )
    result = engine.submit_intent(intent)
    if result.accepted:
        print(f"ORDER ACCEPTED: {result.broker_order_id}")
        if result.fills:
            for f in result.fills:
                print(f"  FILL: {f.quantity} x {f.instrument_id} @ {f.price}")
        if result.cash_balance:
            print(f"  Cash: {result.cash_balance}")
    else:
        print(f"ORDER REJECTED: {result.rejection_reason}")
    _show_status(engine.status())


def cmd_reconcile():
    engine = _build_engine()
    sync = _has_flag("-r") or _has_flag("--from-broker")
    engine.start(sync_from_broker=sync)
    result = engine.reconcile()
    print(f"Reconciliation: {result.severity}")
    for d in result.position_drifts:
        print(f"  {d.instrument_id}: qty_drift={d.quantity_drift}")


def cmd_stop():
    engine = _build_engine()
    try:
        engine.start(sync_from_broker=False)
    except Exception:
        pass
    engine.stop()
    print("Engine stopped.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "buy" or command == "sell":
        args = _get_positional_args()
        if len(args) < 2:
            print(f"Usage: papertrade.py {command} SYMBOL QTY [-r]")
            sys.exit(1)
        symbol, qty = args[0], args[1]
        if command == "buy":
            cmd_buy(symbol, qty)
        else:
            cmd_sell(symbol, qty)
    elif command == "start":
        cmd_start()
    elif command == "status":
        cmd_status()
    elif command == "reconcile":
        cmd_reconcile()
    elif command == "stop":
        cmd_stop()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
