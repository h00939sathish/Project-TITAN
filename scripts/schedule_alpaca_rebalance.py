"""Project TITAN — Automated Alpaca Daily Rebalance Scheduler & Daemon.

Monitors the Alpaca market clock, sleeps until the optimal 10:30 AM ET execution window,
evaluates compliance gates, executes the live paper rebalance batch, and logs receipts to Second Brain.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

from scripts.run_live_paper_session import run_live_paper_rebalance


def wait_and_execute_rebalance(target_hour_et: int = 10, target_minute_et: int = 30, dry_run: bool = False):
    load_dotenv()
    api_key = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        print("ERROR: APCA_API_KEY_ID and APCA_API_SECRET_KEY must be in .env", flush=True)
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=True)
    ny_tz = ZoneInfo("America/New_York")

    print("=" * 78, flush=True)
    print("PROJECT TITAN — ALPACA REBALANCE AUTOMATION DAEMON", flush=True)
    print(f"Target Window: {target_hour_et:02d}:{target_minute_et:02d} AM Eastern Time (Post-Open Auction)", flush=True)
    print(f"Mode:          {'DRY-RUN (Preflight Only)' if dry_run else 'LIVE PAPER EXECUTION'}", flush=True)
    print("=" * 78, flush=True)

    while True:
        try:
            clock = client.get_clock()
            now_et = clock.timestamp.astimezone(ny_tz)
            next_open_et = clock.next_open.astimezone(ny_tz)

            # If weekend or market is closed today, target the next trading day's 10:30 AM ET
            if now_et.weekday() >= 5 or (not clock.is_open and now_et.date() < next_open_et.date()):
                target_et = next_open_et.replace(hour=target_hour_et, minute=target_minute_et, second=0, microsecond=0)
            else:
                target_et = now_et.replace(hour=target_hour_et, minute=target_minute_et, second=0, microsecond=0)
                if (now_et - target_et).total_seconds() > 300:
                    from datetime import timedelta
                    target_et += timedelta(days=1)
                    if target_et.weekday() >= 5:
                        target_et = next_open_et.replace(hour=target_hour_et, minute=target_minute_et, second=0, microsecond=0)

            diff_sec = (target_et - now_et).total_seconds()

            if diff_sec > 60:
                hours = int(diff_sec // 3600)
                minutes = int((diff_sec % 3600) // 60)
                seconds = int(diff_sec % 60)
                print(f"[{now_et.strftime('%H:%M:%S')} ET] Market Open: {clock.is_open}. Waiting for 10:30 AM ET window ({hours}h {minutes}m {seconds}s remaining)...", flush=True)
                
                # Sleep in increments up to 5 minutes, or remaining time if close
                sleep_duration = min(diff_sec - 10, 300.0)
                time.sleep(max(sleep_duration, 10.0))
                continue

            elif diff_sec > 0:
                print(f"[{now_et.strftime('%H:%M:%S')} ET] Window approaching in {diff_sec:.1f}s. Staging execution...", flush=True)
                time.sleep(diff_sec)
                continue

            else:
                # Target window reached!
                print(f"\n[{now_et.strftime('%H:%M:%S')} ET] >>> 10:30 AM ET WINDOW REACHED! TRIGGERING REBALANCE <<<", flush=True)
                
                if not clock.is_open:
                    print("WARNING: Alpaca clock reports market is closed. Checking if today is a trading holiday...", flush=True)

                summary = run_live_paper_rebalance(dry_run=dry_run)
                print(f"Rebalance cycle complete. Orders Dispatched: {summary.orders_dispatched}, Failed: {summary.orders_rejected}", flush=True)
                print("Sleeping for 1800 seconds (30m) before calculating next trading day's rebalance target...", flush=True)
                time.sleep(1800)
                continue

        except KeyboardInterrupt:
            print("\nDaemon interrupted by user. Exiting.", flush=True)
            break
        except Exception as e:
            print(f"Error in scheduler loop: {e}. Retrying in 30 seconds...", flush=True)
            time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TITAN Alpaca Rebalance Scheduler Daemon")
    parser.add_argument("--live", action="store_true", help="Execute live paper orders (default is dry-run)")
    parser.add_argument("--hour", type=int, default=10, help="Target hour in Eastern Time (default 10)")
    parser.add_argument("--minute", type=int, default=30, help="Target minute in Eastern Time (default 30)")
    args = parser.parse_args()

    wait_and_execute_rebalance(
        target_hour_et=args.hour,
        target_minute_et=args.minute,
        dry_run=not args.live,
    )
