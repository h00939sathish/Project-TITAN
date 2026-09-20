#!/usr/bin/env python3
"""Runner CLI script for CRYPTO-004 Live Public WebSocket Shadow Feed.

Connects to public Binance WebSocket and REST streams to maintain real-time
mark-to-market virtual book states, evaluate maker queue fills, and track 8-hour
funding cashflows without any broker credentials or order routing authority.

Usage:
    python scripts/run_crypto_shadow.py --mode ws
    python scripts/run_crypto_shadow.py --mode poll --poll-interval 5.0
    python scripts/run_crypto_shadow.py --mode once --output research/crypto/results/CRYPTO-004-live-shadow-bundle.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure src is in sys.path when executed directly
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from titan.research.crypto_shadow_live import (
    CryptoLiveShadowConfig,
    CryptoLiveShadowService,
)

logger = logging.getLogger("run_crypto_shadow")


def _format_snapshot(snapshot: dict[str, Any]) -> str:
    """Formats a telemetry snapshot for terminal display."""
    ts = snapshot.get("timestamp", "")
    conn = "CONNECTED" if snapshot.get("is_connected") else "DISCONNECTED"
    events = snapshot.get("events_ingested", 0)
    trades = snapshot.get("trades_count", 0)
    pf = snapshot.get("portfolio", {})
    micro = snapshot.get("microstructure", {})

    pnl = pf.get("cumulative_net_pnl", "0.00")
    funding = pf.get("realized_funding", "0.00")
    basis_pnl = pf.get("unrealized_basis_pnl", "0.00")
    fees = pf.get("total_fees", "0.00")
    ret_pct = pf.get("annualized_net_return_pct", 0.0)
    fill_rate = micro.get("maker_fill_rate", 1.0) * 100.0
    unhedged_min = micro.get("mean_unhedged_duration_min", 0.0)

    lines = [
        f"\n[{ts}] CRYPTO-004 LIVE SHADOW STATUS ({conn})",
        f"  Events: {events} | Trades: {trades} | Maker Fill Rate: {fill_rate:.1f}% | Avg Unhedged: {unhedged_min:.2f}m",
        f"  Net P&L: ${float(pnl):+,.2f} | Funding: ${float(funding):+,.2f} | Basis P&L: ${float(basis_pnl):+,.2f} | Fees: ${float(fees):,.2f} | Ann Return: {ret_pct:+.2f}%",
    ]

    symbols_data = snapshot.get("symbols", {})
    for sym, data in symbols_data.items():
        spot = data.get("spot_price") or "N/A"
        perp = data.get("perp_mark_price") or "N/A"
        spread = data.get("basis_spread_bps")
        spread_str = f"{spread:+.2f} bps" if spread is not None else "N/A"
        fund_rate = data.get("funding_rate_8h")
        fund_str = f"{float(fund_rate)*100:+.4f}%" if fund_rate else "N/A"
        ann_fund = data.get("annualized_funding_pct")
        ann_fund_str = f"{ann_fund:+.2f}%" if ann_fund is not None else "N/A"
        pos_p = data.get("position_perp", "0")
        pos_s = data.get("position_spot", "0")
        hedged = data.get("matched_hedged_qty", "0")

        lines.append(
            f"  {sym:<8}: Spot=${spot:<10} Perp=${perp:<10} Basis={spread_str:<12} 8hFund={fund_str:<10} AnnFund={ann_fund_str:<10} Pos(P/S/H)={pos_p}/{pos_s}/{hedged}"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run CRYPTO-004 Non-Custodial Public Live Shadow Feed (ADR-032)"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="BTCUSDT,ETHUSDT",
        help="Comma-separated symbols to track (default: BTCUSDT,ETHUSDT)",
    )
    parser.add_argument(
        "--mode",
        choices=["ws", "poll", "once"],
        default="ws",
        help="Streaming mode: 'ws' (WebSocket streams), 'poll' (periodic REST), 'once' (single REST poll)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="REST poll interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--snapshot-interval",
        type=float,
        default=10.0,
        help="Telemetry snapshot & auto-persist interval in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital in USD (default: 100,000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/crypto/results/CRYPTO-004-live-shadow-bundle.json"),
        help="Output path for shadow evidence bundle JSON",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional max runtime in seconds before clean exit",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    config = CryptoLiveShadowConfig(
        symbols=symbols,
        poll_interval_sec=args.poll_interval,
        snapshot_interval_sec=args.snapshot_interval,
        bundle_output_path=args.output,
        initial_capital=Decimal(str(args.capital)),
    )

    def on_snapshot(snap: dict[str, Any]) -> None:
        print(_format_snapshot(snap), flush=True)

    service = CryptoLiveShadowService(
        config=config,
        on_snapshot_callback=on_snapshot,
    )

    print("=" * 78)
    print("Project TITAN — CRYPTO-004 Live Public Shadow Runner (ADR-032)")
    print(f"Authority: READ_ONLY_SHADOW_NON_CUSTODIAL (Zero Broker Keys / Secrets)")
    print(f"Symbols: {symbols} | Mode: {args.mode} | Output: {config.bundle_output_path}")
    print("=" * 78, flush=True)

    if args.mode == "once":
        print("Executing single REST poll snapshot...")
        events = service.poll_once()
        bundle = service.save_evidence_bundle()
        snapshot = service.get_telemetry_snapshot()
        print(_format_snapshot(snapshot))
        print(f"\nDispatched {len(events)} events. Evidence bundle written to {config.bundle_output_path}")
        return 0

    # Continuous running with signal handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown_handler():
        print("\nShutdown requested (Ctrl+C / SIGINT). Stopping streams and saving bundle...", flush=True)
        service.stop()
        service.save_evidence_bundle()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_handler)

    try:
        if args.mode == "poll":
            loop.run_until_complete(service.run_poll_loop_async(duration_sec=args.duration))
        else:
            loop.run_until_complete(service.run_async(duration_sec=args.duration))
    except KeyboardInterrupt:
        shutdown_handler()
    finally:
        service.save_evidence_bundle()
        snap = service.get_telemetry_snapshot()
        print(_format_snapshot(snap))
        print(f"\nLive shadow run completed. Canonical evidence bundle saved to: {config.bundle_output_path}")
        loop.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
