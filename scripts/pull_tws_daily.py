"""Pull long TWS daily-bar history for FX pairs (for daily-scale TSM research).

One request per symbol (instant): barSize '1 day', duration '5 Y', MIDPOINT for
CASH contracts. Writes research/tws_daily/{SYMBOL}.json (OHLCV).

Run:  python scripts/pull_tws_daily.py
"""
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

SYMBOLS = ["EURUSD", "GBPUSD"]
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "tws_daily"


class DailyCollector(EWrapper, EClient):
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
        if errorCode not in (2104, 2106, 2158, 2159, 10167, 10197, 202):
            print(f"[daily] Err {errorCode}: {errorString}", flush=True)


def main():
    collector = DailyCollector()
    collector._instr_by_req = {}
    collector.connect("127.0.0.1", 7497, 181)
    t = threading.Thread(target=collector.run, daemon=True)
    t.start()
    if not collector._ready.wait(timeout=15):
        print("FATAL: no nextValidId — is TWS up?")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i, sym in enumerate(SYMBOLS):
        req_id = 9100 + i
        collector._instr_by_req[req_id] = sym
        c = _contract(sym)
        what = "MIDPOINT" if c.secType == "CASH" else "TRADES"
        collector.bars[req_id] = []
        collector.done[req_id] = False
        collector.reqHistoricalData(
            req_id, c, "", "5 Y", "1 day", what,
            1, 2, False, [],
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not collector.done.get(req_id):
            time.sleep(0.5)
        bars = collector.bars[req_id]
        out = OUT_DIR / f"{sym}.json"
        out.write_text(json.dumps(bars, indent=1), encoding="utf-8")
        span = f"{bars[0]['timestamp'][:10]} -> {bars[-1]['timestamp'][:10]}" if bars else "EMPTY"
        print(f"{sym}: {len(bars)} daily bars ({span})", flush=True)
        time.sleep(1.5)

    collector.disconnect()


if __name__ == "__main__":
    main()
