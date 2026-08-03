"""Pull real TWS 5-minute RTH OHLCV history for the session instruments.

Writes research/tws_history/<SYMBOL>.json (list of bar dicts with
instrument_id/timestamp/open/high/low/close/volume). Same data source and
contract mapping as the live session feed.

Run:  python scripts/pull_tws_history.py [--duration "2 M"] [--symbol SPY]
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from titan.data.tws_feed import _contract

SYMBOLS = ["SPY", "QQQ", "IWM", "EURUSD", "GBPUSD", "AAPL", "MSFT", "XLF", "XLK"]
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "tws_history"


class HistoryCollector(EWrapper, EClient):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self._ready = threading.Event()
        self.bars: dict[int, list[dict]] = {}
        self.done: dict[int, bool] = {}

    def nextValidId(self, orderId: int) -> None:
        self._ready.set()

    def historicalData(self, req_id: int, bar) -> None:
        ts = datetime.fromtimestamp(float(bar.date), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.bars.setdefault(req_id, []).append({
            "instrument_id": self._instr_by_req[req_id],
            "timestamp": ts,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        })

    def historicalDataEnd(self, req_id: int, start: str, end: str) -> None:
        self.done[req_id] = True

    def error(self, reqId: int, errorTime: int = -1, errorCode: int = 0,
              errorString: str = "", advancedOrderRejectJson: str = "") -> None:
        # 162 = pacing violation (expected if requests are too close); the sleep
        # between requests avoids it. 10167/10197 delayed data is normal on paper.
        if errorCode not in (2104, 2106, 2158, 2159, 10167, 10197, 202):
            print(f"[history] Err {errorCode}: {errorString}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", default="2 M", help="TWS duration string (e.g. '1 M', '2 M')")
    ap.add_argument("--symbol", default=None)
    args = ap.parse_args()
    symbols = [args.symbol] if args.symbol else SYMBOLS

    collector = HistoryCollector()
    collector._instr_by_req = {}
    collector.connect("127.0.0.1", 7497, 180)
    t = threading.Thread(target=collector.run, daemon=True)
    t.start()
    if not collector._ready.wait(timeout=15):
        print("FATAL: no nextValidId — is TWS up?")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, sym in enumerate(symbols):
        req_id = 9000 + i
        collector._instr_by_req[req_id] = sym
        c = _contract(sym)
        what = "TRADES" if c.secType != "CASH" else "MIDPOINT"
        collector.bars[req_id] = []
        collector.done[req_id] = False
        collector.reqHistoricalData(
            req_id, c, "", args.duration, "5 mins", what,
            1, 2, False, [],  # useRTH=1, formatDate=2 (epoch), keepUpToDate=False
        )
        # Pacing: wait for completion + 10.5s between requests.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not collector.done.get(req_id):
            time.sleep(0.5)
        time.sleep(10.5)

        bars = collector.bars[req_id]
        out = OUT_DIR / f"{sym}.json"
        out.write_text(json.dumps(bars, indent=1), encoding="utf-8")
        span = f"{bars[0]['timestamp'][:10]} -> {bars[-1]['timestamp'][:10]}" if bars else "EMPTY"
        print(f"{sym}: {len(bars)} bars ({span}) -> {out}", flush=True)

    collector.disconnect()


if __name__ == "__main__":
    main()
