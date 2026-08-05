"""Weekend rehearsal: replay real TWS 5-min bars through the signal path.

Read-only — no orders are placed. Mirrors the live session exactly:
  - feeds Friday's real completed bars through the same ma-crossover bridge,
    calling on_price ONLY for bars inside the RTH window (09:35-16:00 ET,
    weekdays) exactly like the session's gate does
  - records every intent that would have fired, then applies the risk gate and
    the account's funding reality (USD cash ~-27) to estimate broker behavior

Run:  python scripts/weekend_rehearsal.py [--instrument EURUSD]
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from titan._core import Money, RiskConfig, RiskGate
from titan.data.forex_pairs import FOREX_SYMBOLS, STEP_SIZE, forex_instrument
from titan.data.tws_feed import TWSRealtimeFeed
from titan.strategies.bridge import StrategyBridge

INSTRUMENTS = ["SPY", "QQQ", "IWM", "EURUSD", "GBPUSD", "AAPL", "MSFT", "XLF", "XLK"]
BAR_SIZE = "5 mins"
ET = ZoneInfo("US/Eastern")


def in_rth(ts_utc: datetime) -> bool:
    et = ts_utc.astimezone(ET)
    if et.weekday() >= 5:
        return False
    return (9 <= et.hour < 16) and (et.hour != 9 or et.minute >= 35)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default=None)
    args = ap.parse_args()
    instruments = [args.instrument] if args.instrument else INSTRUMENTS

    rc = RiskConfig(
        INSTRUMENTS, Money("100000", "USD"), 1000, 5000,
        Money("100000", "USD"), 0.10, Money("5000", "USD"), 5000, 100,
    )
    gate = RiskGate(rc)

    lot_sizes = {}
    for i in INSTRUMENTS:
        if i in FOREX_SYMBOLS:
            inst = forex_instrument(i)
            lot_sizes[i] = inst.step_size if inst else STEP_SIZE
        else:
            lot_sizes[i] = 1

    bridge = StrategyBridge(
        strategy_id="ma-crossover",
        strategy_params={"fast": 5, "slow": 20},
        account_id="paper-1",
        order_size=1,
        lot_sizes=lot_sizes,
    )

    print("=" * 78)
    print(f"WEEKEND REHEARSAL — Friday's real TWS {BAR_SIZE} bars through the signal path")
    print("Read-only: no orders placed. Bridge sees ONLY RTH bars, like the live session.")
    print("=" * 78)

    feed = TWSRealtimeFeed(
        instruments=instruments, bar_size=BAR_SIZE, client_id=152,
        host="127.0.0.1", port=7497, duration="1 D",
    )
    try:
        # Backfill arrives asynchronously after subscribe — give it time to land.
        import time
        time.sleep(8)
        bars = {i: feed.completed_bars(i) for i in instruments}
    finally:
        feed.disconnect()

    total = 0
    for instr in instruments:
        series = bars.get(instr, [])
        if not series:
            print(f"\n{instr}: no bars")
            continue
        print(f"\n{instr}: {len(series)} bars "
              f"({series[0][0][:16]} -> {series[-1][0][:16]} UTC)")

        fired = []
        for ts_str, close in series:
            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if not in_rth(ts):
                continue  # session gate: non-RTH bars never reach the bridge
            # The live session passes the FULL bar timestamp as bar_date (per-bar
            # dedup) — NOT the date, which would dedup the whole day away.
            intent = bridge.on_price(instr, close, bar_date=ts_str)
            if intent is None:
                continue
            qty = int(intent.quantity)
            notional = qty * float(intent.price)
            verdict = gate.evaluate(intent)
            if instr in FOREX_SYMBOLS:
                broker = "fills (short, builds USD)" if intent.side == "SELL" \
                    else f"TWS REJECTS (~${notional:,.0f} needed, USD ~-27)"
            else:
                broker = "likely fills" if (intent.side == "SELL" or notional < 100) \
                    else f"TWS likely REJECTS (~${notional:,.0f} needed)"
            fired.append({
                "ts": ts.astimezone(ET).strftime("%H:%M ET"),
                "side": intent.side, "qty": qty, "price": intent.price,
                "notional": round(notional, 2),
                "risk": "ACCEPT" if verdict.accepted else "REJECT",
                "broker": broker,
            })
        total += len(fired)
        if not fired:
            print("  no intents (no crossover flips within the RTH window)")
        for f in fired:
            print(f"  {f['ts']}  {f['side']:4} qty={f['qty']:>5} @ {f['price']:>10} "
                  f"notional=${f['notional']:>9.2f} | risk={f['risk']} | {f['broker']}")

    print("\n" + "=" * 78)
    print(f"Rehearsal complete: {total} intents would have fired on Friday's real data.")


if __name__ == "__main__":
    main()
