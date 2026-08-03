"""Reconcile Alpaca paper account and cancel open orders after incident.

Usage:
    python scripts/reconcile_and_cancel.py                          # dry-run (default)
    python scripts/reconcile_and_cancel.py --execute                # actually cancels orders
    python scripts/reconcile_and_cancel.py --liquidate              # sell all positions to cash

Output:
    - Prints open orders, positions, and reconciliation diff to stdout
    - Saves reconciliation and liquidation reports to incident-evidence/
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

from dotenv import load_dotenv

from titan.execution.alpaca_adapter import create_broker_paper_adapter
from titan._core import Money


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Reconcile Alpaca paper account after incident")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Actually cancel open orders (default: dry-run)")
    parser.add_argument("--liquidate", action="store_true", default=False,
                        help="Sell all positions to cash (implies --execute)")
    args = parser.parse_args()

    adapter = create_broker_paper_adapter()
    adapter.authenticate()
    client = adapter._ensure_client()

    report_dir = Path("incident-evidence")
    report_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"reconciliation-{ts}.json"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "liquidate" if args.liquidate else ("execute" if args.execute else "dry-run"),
    }

    do_cancel = args.execute or args.liquidate

    # --- Cancel open orders ---
    try:
        open_orders = client.get_orders()
        open_orders = [o for o in open_orders if o.status.value == "open"]
        report["open_orders"] = [
            {"id": str(o.id), "symbol": o.symbol, "side": str(o.side),
             "qty": str(o.qty), "type": str(o.type), "status": str(o.status)}
            for o in open_orders
        ]
        if do_cancel:
            for o in open_orders:
                client.cancel_order(o.id)
                print(f"Cancelled order {o.id} ({o.symbol} {o.side} {o.qty})", flush=True)
        else:
            for o in open_orders:
                print(f"[DRY-RUN] Would cancel order {o.id} ({o.symbol} {o.side} {o.qty})", flush=True)
        report["orders_cancelled"] = len(open_orders)
    except Exception as e:
        report["orders_error"] = str(e)
        print(f"Error fetching/cancelling orders: {e}", flush=True)

    # --- Snapshot positions from Alpaca ---
    try:
        pos_snapshot = adapter.positions("default")
        alpaca_positions = {}
        for p in pos_snapshot.positions:
            instr = str(p.instrument_id)
            alpaca_positions[instr] = {
                "quantity": int(p.quantity),
                "side": p.side,
            }
        report["alpaca_positions"] = alpaca_positions
        print(f"\nAlpaca positions:", flush=True)
        for instr, data in alpaca_positions.items():
            print(f"  {instr}: {data['side']} {data['quantity']}", flush=True)
    except Exception as e:
        report["positions_error"] = str(e)
        print(f"Error fetching positions: {e}", flush=True)

    # --- Load local portfolio from EventStore for comparison ---
    try:
        from titan._core import EventStore
        store = EventStore(str(Path(".titan_state.db")))
        events = store.replay_by_type("PortfolioState")
        if events:
            local_state = json.loads(events[-1].payload)
        else:
            local_state = {}
    except Exception:
        local_state = {}

    if local_state:
        local_positions = {}
        for instr, p in local_state.get("portfolio", {}).get("positions", {}).items():
            local_positions[instr] = {"quantity": p.get("quantity", 0), "side": p.get("side", "")}
        report["local_positions"] = local_positions
        print(f"\nLocal EventStore positions:", flush=True)
        for instr, data in local_positions.items():
            print(f"  Local  {instr}: {data['side']} {data['quantity']}", flush=True)

        all_keys = set(alpaca_positions.keys()) | set(local_positions.keys())
        diffs = []
        for k in sorted(all_keys):
            a = alpaca_positions.get(k, {})
            l = local_positions.get(k, {})
            a_qty = a.get("quantity", 0)
            l_qty = l.get("quantity", 0)
            if a_qty != l_qty:
                diffs.append({"instrument": k, "alpaca_qty": a_qty, "local_qty": l_qty})
        report["reconciliation_diffs"] = diffs
        if diffs:
            print(f"\nReconciliation diffs:", flush=True)
            for d in diffs:
                print(f"  MISMATCH {d['instrument']}: Alpaca={d['alpaca_qty']} Local={d['local_qty']}", flush=True)
        else:
            print(f"\nAll positions match.", flush=True)
    else:
        report["local_positions"] = None
        print(f"\nNo local portfolio found in EventStore.", flush=True)

    # --- Liquidate if requested ---
    if args.liquidate:
        print(f"\nLiquidating all positions...", flush=True)
        liquidated = []
        for instr, data in alpaca_positions.items():
            qty = data["quantity"]
            if qty <= 0:
                continue
            try:
                from titan.execution.alpaca_adapter import MarketOrderRequest, OrderType, TimeInForce
                from alpaca.trading.models import OrderSide
                request = MarketOrderRequest(
                    symbol=instr,
                    qty=str(qty),
                    side=OrderSide.SELL,
                    type=OrderType.MARKET,
                    time_in_force=TimeInForce.DAY,
                )
                result = client.submit_order(request)
                liquidated.append({"instrument": instr, "qty": qty, "order_id": str(result.id)})
                print(f"  Sold {qty} {instr} -> order {result.id}", flush=True)
            except Exception as e:
                liquidated.append({"instrument": instr, "qty": qty, "error": str(e)})
                print(f"  FAILED to sell {instr}: {e}", flush=True)
        report["liquidated"] = liquidated
        print(f"\nLiquidation complete.", flush=True)

    # --- Save report ---
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nReport saved to {report_path}", flush=True)


if __name__ == "__main__":
    main()
