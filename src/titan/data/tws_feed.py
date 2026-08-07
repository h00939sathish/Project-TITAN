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
        self._host = host
        self._port = port
        self._base_cid = client_id
        self._connect_timeout = connect_timeout

        self._ready = threading.Event()
        self._lock = threading.Lock()
        # instr -> list of (iso_ts, close) for COMPLETED bars only
        self._bars: dict[str, list[tuple[str, float]]] = {i: [] for i in instruments}
        # instr -> list of full-OHLC completed bars (same promotion lifecycle)
        self._bars_ohlc: dict[str, list[dict]] = {i: [] for i in instruments}
        # instr -> (ts, close) of the currently forming bar (not exposed)
        self._forming: dict[str, tuple[str, float] | None] = {i: None for i in instruments}
        # instr -> forming bar full OHLC (not exposed)
        self._forming_ohlc: dict[str, dict | None] = {i: None for i in instruments}
        self._instr_by_req: dict[int, str] = {}

        # Feed-recovery state: disconnect/error storms must trigger a
        # reconnect + resubscribe, and a stalled feed must fail closed.
        self._storm_codes = frozenset(
            {1100, 2110, 2103, 2105, 2107, 2108, 10182, 10187, 10191, 202}
        )
        self._err_storm = 0
        self._recovery_needed = False
        self._recovering = False
        self._last_update = time.monotonic()
        self._has_any_bar = False

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
            ohlc = {
                "timestamp": ts,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": close,
                "volume": int(float(bar.volume)) if bar.volume and float(bar.volume) > 0 else 0,
            }
            with self._lock:
                self._last_update = time.monotonic()
                self._has_any_bar = True
                forming = self._forming.get(instr)
                if forming is not None and forming[0] != ts:
                    # previous bar completed → promote to completed list
                    self._bars[instr].append(forming)
                    fl = self._forming_ohlc.get(instr)
                    if fl is not None:
                        self._bars_ohlc[instr].append(fl)
                    if len(self._bars[instr]) > self._window:
                        self._bars[instr] = self._bars[instr][-self._window:]
                        self._bars_ohlc[instr] = self._bars_ohlc[instr][-self._window:]
                self._forming[instr] = (ts, close)
                self._forming_ohlc[instr] = ohlc

    def error(self, req_id: int, errorTime: int = -1, errorCode: int = 0,
              errorString: str = "", advancedOrderRejectJson: str = "") -> None:
        # Connectivity/farm/stream-loss codes. A storm of these (or a lone 1100
        # disconnect) means the bars have silently stopped advancing; mark the
        # feed for recovery so the session can reconnect + resubscribe.
        if errorCode == 1102:  # connectivity restored
            self._err_storm = 0
            return
        if errorCode in self._storm_codes:
            self._err_storm += 1
            if self._err_storm >= 3:
                self._recovery_needed = True
                self._err_storm = 0
            if errorCode == 1100:
                # A full disconnect should recover on its own, not wait for a 3-storm.
                self._recovery_needed = True
        # 10167/10197 = delayed data (paper account, no realtime subscription) — normal
        elif errorCode not in (2104, 2106, 2158, 2159, 10167, 10197):
            print(f"[tws_realtime] Err {errorCode}: {errorString}", flush=True)

    # ── feed recovery (disconnect/reconnect + resubscribe, fail-closed) ──────
    def needs_recovery(self) -> bool:
        return bool(self._recovery_needed or self._recovering)

    def recover(self) -> None:
        """Reconnect and resubscribe every contract after a disconnect/error
        storm. Keeps existing completed bars (for continuity) but resets the
        forming bar so a fresh transition re-promotes on the next push."""
        if self._recovering:
            return
        self._recovering = True
        try:
            self._ready.clear()
            try:
                self.disconnect()
            except Exception:
                pass
            import random
            cid = self._base_cid if self._base_cid != 150 else random.randint(300, 800)
            self.connect(self._host, self._port, cid)
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
            if not self._ready.wait(timeout=self._connect_timeout):
                raise ConnectionError("TWSRealtimeFeed: reconnect timed out")
            with self._lock:
                self._forming = {i: None for i in self._instruments}
                self._forming_ohlc = {i: None for i in self._instruments}
            self._subscribe()
            self._recovery_needed = False
            self._err_storm = 0
            self._last_update = time.monotonic()
        finally:
            self._recovering = False



    def is_healthy(self, stale_after_s: float = 30.0) -> bool:
        """False while recovering or when bar pushes have stalled beyond
        stale_after_s (but only once we've seen at least one bar)."""
        if self._recovering:
            return False
        if self._has_any_bar and time.monotonic() - self._last_update > stale_after_s:
            return False
        return True

    def bars_advancing(self, since_ts: str | None = None) -> bool:
        """True if any completed bar is newer than since_ts (feed advanced)."""
        with self._lock:
            for bars in self._bars.values():
                if bars and (since_ts is None or bars[-1][0] > since_ts):
                    return True
        return False

    def latest_ts(self) -> str | None:
        """Most recent completed-bar timestamp across all instruments, or None."""
        with self._lock:
            latest = None
            for bars in self._bars.values():
                if bars and (latest is None or bars[-1][0] > latest):
                    latest = bars[-1][0]
            return latest

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

    def completed_ohlc(self, instr: str) -> list[dict]:
        """Return completed bars as full-OHLC dicts (open/high/low/close/volume).

        Guaranteed to be the same bars and order as ``completed_bars`` (same
        promotion lifecycle), so a strategy can use the OHLC path for intrabar
        stop/trail logic without double-count. Never includes the forming bar.
        """
        with self._lock:
            return list(self._bars_ohlc.get(instr, []))

    def latest_completed_ohlc(self, instr: str) -> dict | None:
        bars = self.completed_ohlc(instr)
        return bars[-1] if bars else None

    def latest_completed(self, instr: str) -> tuple[str, float] | None:
        bars = self.completed_bars(instr)
        return bars[-1] if bars else None
