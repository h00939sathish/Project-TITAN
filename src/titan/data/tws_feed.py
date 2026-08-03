"""TWS data feed — fetches daily bars via IBKR Trader Workstation."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


_REQ_MAP: dict[str, Contract] = {}


def _contract(instr: str) -> Contract:
    c = Contract()
    if instr == "SPY":
        c.symbol = "SPY"; c.secType = "STK"; c.exchange = "ARCA"; c.currency = "USD"
    elif instr == "QQQ":
        c.symbol = "QQQ"; c.secType = "STK"; c.exchange = "ISLAND"; c.currency = "USD"
    elif instr == "TLT":
        c.symbol = "TLT"; c.secType = "STK"; c.exchange = "ISLAND"; c.currency = "USD"
    elif instr == "IWM":
        c.symbol = "IWM"; c.secType = "STK"; c.exchange = "ISLAND"; c.currency = "USD"
    elif instr == "AAPL":
        c.symbol = "AAPL"; c.secType = "STK"; c.exchange = "ISLAND"; c.currency = "USD"
    elif instr == "MSFT":
        c.symbol = "MSFT"; c.secType = "STK"; c.exchange = "ISLAND"; c.currency = "USD"
    elif instr in ("EURUSD", "EUR.USD"):
        c.symbol = "EUR"; c.secType = "CASH"; c.exchange = "IDEALPRO"; c.currency = "USD"
    elif instr in ("GBPUSD", "GBP.USD"):
        c.symbol = "GBP"; c.secType = "CASH"; c.exchange = "IDEALPRO"; c.currency = "USD"
    elif instr in ("AUDUSD", "AUD.USD"):
        c.symbol = "AUD"; c.secType = "CASH"; c.exchange = "IDEALPRO"; c.currency = "USD"
    elif instr in ("XAUUSD", "XAU.USD"):
        c.symbol = "XAU"; c.secType = "CASH"; c.exchange = "IDEALPRO"; c.currency = "USD"
    elif instr in ("NZDUSD", "NZD.USD"):
        c.symbol = "NZD"; c.secType = "CASH"; c.exchange = "IDEALPRO"; c.currency = "USD"
    else:
        c.symbol = instr; c.secType = "STK"; c.exchange = "SMART"; c.currency = "USD"
    return c


class _IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self._done = threading.Event()
        self._bars: list[dict] = []
        self._error_code: int | None = None

    def historicalData(self, req_id: int, bar):
        self._bars.append({
            "timestamp": bar.date,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": int(float(bar.volume)) if bar.volume and float(bar.volume) > 0 else 0,
        })

    def historicalDataEnd(self, req_id: int, start: str, end: str):
        self._done.set()

    def error(self, req_id: int, code: int, msg: str, *args):
        if code not in (2104, 2106, 2158):
            self._error_code = code


class TWSDataFeed:
    """Fetches bars from TWS for paper_session live data & qualification.

    Usage:
        feed = TWSDataFeed()
        bars = feed.fetch_to_approved("EURUSD", bar_size="1 hour", duration="1 M")
        feed.disconnect()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497,
                 client_id: int = 1203, timeout_sec: float = 3.0):

        self._host = host
        self._port = port
        self._client_id = client_id
        self._timeout = timeout_sec
        self._req_id = 9000
        self._wrapper = _IBWrapper()
        self._client = EClient(self._wrapper)
        self._client.connect(host, port, client_id)
        self._thread = threading.Thread(target=self._client.run, daemon=True)
        self._thread.start()

        start_time = time.time()
        while self._client.serverVersion() is None and (time.time() - start_time) < self._timeout:
            time.sleep(0.1)

    def fetch_to_approved(self, instrument_id: str, bar_size: str = "1 day", duration: str = "2 Y") -> list[dict]:
        """Fetch bars matching paper_session StrategyRunner interface."""
        if self._client.serverVersion() is None:
            return []

        self._req_id += 1
        self._wrapper._bars = []
        self._wrapper._error_code = None
        self._wrapper._done.clear()

        try:
            c = _contract(instrument_id)
            what_to_show = "TRADES" if c.secType != "CASH" else "MIDPOINT"
            self._client.reqHistoricalData(
                self._req_id, c, "", duration, bar_size, what_to_show,
                1, 1, False, [],
            )
            self._wrapper._done.wait(self._timeout)
        except Exception:
            return []


        result = list(self._wrapper._bars)
        if not result:
            return []
        result.sort(key=lambda b: b.get("timestamp", ""))
        return result

    def disconnect(self):
        self._client.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()


class TWSRealtimeFeed(EWrapper, EClient):
    """Streams completed intraday bars from TWS (reqHistoricalData keepUpToDate).

    Each instrument is subscribed with a historical request whose last bar is
    kept ``keepUpToDate`` — TWS re-delivers the forming bar on every update and
    moves to a new timestamp when a bar completes. This class exposes only
    *completed* bars, so callers never trade on an in-progress bar.

    Usage:
        feed = TWSRealtimeFeed(["SPY", "XLF"], bar_size="5 mins")
        bars = feed.completed_bars("SPY")   # [(iso_ts, close), ...], thread-safe
        feed.disconnect()
    """

    def __init__(
        self,
        instruments: list[str],
        bar_size: str = "5 mins",
        duration: str = "1 D",
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 150,
        window: int = 500,
        connect_timeout: float = 10.0,
    ) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, self)

        self._instruments = list(instruments)
        self._bar_size = bar_size
        self._duration = duration
        self._window = window

        self._ready = threading.Event()
        self._lock = threading.Lock()
        # instr -> list of (iso_ts, close) for COMPLETED bars only
        self._bars: dict[str, list[tuple[str, float]]] = {i: [] for i in instruments}
        # instr -> (ts, close) of the currently forming bar (not exposed)
        self._forming: dict[str, tuple[str, float] | None] = {i: None for i in instruments}
        self._instr_by_req: dict[int, str] = {}

        import random
        base_cid = client_id if client_id != 150 else random.randint(300, 800)
        self.connect(host, port, base_cid)
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=connect_timeout):
            self.disconnect()
            raise ConnectionError(f"TWSRealtimeFeed: no nextValidId within {connect_timeout}s")
        self._subscribe()



    # ── ibapi callbacks (client thread) ─────────────────────────────────────
    def nextValidId(self, orderId: int) -> None:
        self._ready.set()

    def historicalData(self, req_id: int, bar) -> None:
        instr = self._instr_by_req.get(req_id)
        if instr is None:
            return
        # formatDate=2 → bar.date is epoch seconds (UTC)
        ts = datetime.fromtimestamp(float(bar.date), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        close = float(bar.close)
        with self._lock:
            forming = self._forming.get(instr)
            if forming is not None and forming[0] != ts:
                # previous bar completed → promote to completed list
                self._bars[instr].append(forming)
                if len(self._bars[instr]) > self._window:
                    self._bars[instr] = self._bars[instr][-self._window:]
            self._forming[instr] = (ts, close)

    def error(self, req_id: int, errorTime: int = -1, errorCode: int = 0,
              errorString: str = "", advancedOrderRejectJson: str = "") -> None:
        # 10167/10197 = delayed data (paper account, no realtime subscription) — normal
        if errorCode not in (2104, 2106, 2158, 2159, 10167, 10197, 202):
            print(f"[tws_realtime] Err {errorCode}: {errorString}", flush=True)

    # ── public API ──────────────────────────────────────────────────────────
    def _subscribe(self) -> None:
        for i, instr in enumerate(self._instruments):
            req_id = 8000 + i
            self._instr_by_req[req_id] = instr
            c = _contract(instr)
            what_to_show = "TRADES" if c.secType != "CASH" else "MIDPOINT"
            self.reqHistoricalData(
                req_id, c, "", self._duration, self._bar_size, what_to_show,
                1, 2, True, [],  # useRTH=1, formatDate=2 (epoch), keepUpToDate=True
            )

    def completed_bars(self, instr: str) -> list[tuple[str, float]]:
        """Return completed bars as [(iso_ts, close)] — never the forming bar."""
        with self._lock:
            return list(self._bars.get(instr, []))

    def latest_completed(self, instr: str) -> tuple[str, float] | None:
        bars = self.completed_bars(instr)
        return bars[-1] if bars else None
