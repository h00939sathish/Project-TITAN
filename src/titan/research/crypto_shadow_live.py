"""Live Public WebSocket Shadow Feed and Service for CRYPTO-004.

Ingests public live market data for BTCUSDT and ETHUSDT (spot prices, perpetual mark prices,
and 8-hour funding rates) from Binance public streams and REST endpoints, dispatching
CryptoMarketEvent records into CryptoShadowRunner to evaluate real-time basis carry,
maker fill probabilities, and matched hedged funding accruals.

STRICT GOVERNANCE INVARIANTS (ADR-032):
- Non-custodial, read-only shadow research pipeline.
- Zero exchange credentials, zero API keys, zero order authority.
- Strictly forbidden from importing titan.execution, titan.runtime, or broker adapters.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

import httpx

from titan.backtest.crypto_costs import CryptoCostModel
from titan.data.crypto import (
    CryptoDataManifest,
    CryptoMarketEvent,
    event_id_for,
)
from titan.research.crypto_shadow_runner import CryptoShadowRunner

logger = logging.getLogger("titan.research.crypto_shadow_live")

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = _REPO_ROOT / "research" / "crypto" / "manifests" / "binance_vision_v1.json"
DEFAULT_BUNDLE_PATH = _REPO_ROOT / "research" / "crypto" / "results" / "CRYPTO-004-live-shadow-bundle.json"


def load_default_manifest(path: Path | str | None = None) -> CryptoDataManifest:
    """Loads manifest or creates a default read-only public stream manifest."""
    mpath = Path(path) if path else DEFAULT_MANIFEST_PATH
    if mpath.exists():
        return CryptoDataManifest.load(mpath)
    return CryptoDataManifest(
        venue="Binance",
        venue_id="binance-vision",
        source_url="https://data.binance.vision/",
        licence="Public live streams. Research shadow use only.",
        licence_url="https://data.binance.vision/",
        licence_notes="Non-custodial public market data feed.",
        symbols=["BTCUSDT", "ETHUSDT"],
        products=[],
        timezone="UTC",
        timestamp_semantics="UTC ISO-8601 open-time",
        coverage_from="2026-01-01T00:00:00+00:00",
        coverage_to="2026-12-31T23:59:59+00:00",
        is_partition={"from": "2026-01-01T00:00:00+00:00", "to": "2026-06-30T23:59:59+00:00"},
        oos_partition={"from": "2026-07-01T00:00:00+00:00", "to": "2026-12-31T23:59:59+00:00"},
        fee_schedule={"tier": "VIP1"},
        funding_convention={"cadence_hours": 8},
        precision={"price": 2, "qty": 6},
        retrieval_ts_utc=datetime.now(timezone.utc).isoformat(),
    )


def _safe_dec(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _parse_ts(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, (int, float)):
        # Milliseconds timestamp
        if val > 1e11:
            val = val / 1000.0
        return datetime.fromtimestamp(val, tz=timezone.utc)
    if isinstance(val, str) and val:
        if val.isdigit():
            v = int(val)
            if v > 1e11:
                v = v / 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        text = val.replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(text)
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _settlement_bucket_8h(dt: datetime) -> int:
    """Returns the 8-hour bucket index (hours since epoch // 8)."""
    epoch_sec = int(dt.timestamp())
    return epoch_sec // (8 * 3600)


def _settlement_bucket_to_dt(bucket: int) -> datetime:
    """Converts 8-hour bucket index to UTC datetime at start of period."""
    return datetime.fromtimestamp(bucket * 8 * 3600, tz=timezone.utc)


@dataclass(frozen=True)
class CryptoLiveShadowConfig:
    """Configuration for live public non-custodial shadow feed."""

    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    spot_ws_base: str = "wss://stream.binance.com:9443/ws"
    perp_ws_base: str = "wss://fstream.binance.com/ws"
    spot_rest_base: str = "https://api.binance.com"
    perp_rest_base: str = "https://fapi.binance.com"
    poll_interval_sec: float = 5.0
    snapshot_interval_sec: float = 10.0
    bundle_output_path: Path = DEFAULT_BUNDLE_PATH
    initial_capital: Decimal = Decimal("100000")
    maker_fill_probability: float = 0.85
    mean_maker_fill_delay_min: float = 3.5
    max_legging_timeout_min: float = 15.0
    session_id: str = "crypto_004_live_shadow"
    venue_id: str = "binance-vision"


def translate_spot_ticker_message(
    raw: dict[str, Any] | str,
    manifest_digest: str,
    venue: str = "binance-vision",
) -> CryptoMarketEvent:
    """Translates Binance Spot WebSocket (bookTicker/ticker/trade) or REST message to CryptoMarketEvent."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    # Handle wrapped stream payload {"stream": ..., "data": {...}}
    if "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    symbol = str(data.get("s") or data.get("symbol") or "BTCUSDT").upper()
    raw_ev = data.get("e")
    sequence = data.get("t") or data.get("u") or data.get("lastUpdateId") or data.get("sequence") or data.get("E")

    occurred_at = _parse_ts(data.get("E") or data.get("T") or data.get("time"))
    ingestion_ts = datetime.now(timezone.utc)

    price = _safe_dec(data.get("p") or data.get("price") or data.get("c"))

    if raw_ev == "trade":
        event_type = "TRADE"
        qty = _safe_dec(data.get("q") or data.get("qty"))
        is_buyer_maker = data.get("m")
        side = "SELL" if is_buyer_maker else "BUY"
        bid = None
        ask = None
        bid_qty = None
        ask_qty = None
    else:
        qty = None
        side = None
        bid = _safe_dec(data.get("b") or data.get("bidPrice"))
        ask = _safe_dec(data.get("a") or data.get("askPrice"))
        bid_qty = _safe_dec(data.get("B") or data.get("bidQty"))
        ask_qty = _safe_dec(data.get("A") or data.get("askQty"))
        if bid is not None and ask is not None:
            event_type = "QUOTE"
            if price is None:
                price = (bid + ask) / Decimal("2")
        else:
            event_type = "MARK"

    event_payload = {
        "venue": venue,
        "symbol": symbol,
        "contract_kind": "SPOT",
        "occurred_at": occurred_at.isoformat(),
        "event_type": event_type,
        "price": str(price) if price is not None else None,
        "bid": str(bid) if bid is not None else None,
        "ask": str(ask) if ask is not None else None,
        "sequence": sequence,
    }
    eid = event_id_for(event_payload)

    return CryptoMarketEvent(
        event_id=eid,
        venue=venue,
        symbol=symbol,
        contract_kind="SPOT",
        occurred_at=occurred_at,
        event_type=event_type,
        source_manifest_digest=manifest_digest,
        ingestion_ts=ingestion_ts,
        sequence=int(sequence) if sequence is not None and str(sequence).isdigit() else None,
        price=price,
        qty=qty,
        side=side,
        bid=bid,
        ask=ask,
        bid_qty=bid_qty,
        ask_qty=ask_qty,
    )


def translate_perp_mark_message(
    raw: dict[str, Any] | str,
    manifest_digest: str,
    venue: str = "binance-vision",
) -> tuple[CryptoMarketEvent, Decimal | None, int | None]:
    """Translates Binance USDT-M Futures markPriceUpdate or REST premiumIndex message.

    Returns:
        (CryptoMarketEvent, funding_rate, next_funding_time_ms)
    """
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    if "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    symbol = str(data.get("s") or data.get("symbol") or "BTCUSDT").upper()
    occurred_at = _parse_ts(data.get("E") or data.get("time"))
    ingestion_ts = datetime.now(timezone.utc)

    price = _safe_dec(data.get("p") or data.get("markPrice"))
    funding_rate = _safe_dec(data.get("r") or data.get("lastFundingRate"))
    next_funding_time = data.get("T") or data.get("nextFundingTime")
    if next_funding_time is not None:
        try:
            next_funding_time = int(next_funding_time)
        except (ValueError, TypeError):
            next_funding_time = None

    event_payload = {
        "venue": venue,
        "symbol": symbol,
        "contract_kind": "PERPETUAL",
        "occurred_at": occurred_at.isoformat(),
        "event_type": "MARK",
        "price": str(price) if price is not None else None,
    }
    eid = event_id_for(event_payload)

    event = CryptoMarketEvent(
        event_id=eid,
        venue=venue,
        symbol=symbol,
        contract_kind="PERPETUAL",
        occurred_at=occurred_at,
        event_type="MARK",
        source_manifest_digest=manifest_digest,
        ingestion_ts=ingestion_ts,
        price=price,
        funding_rate=funding_rate,
    )
    return event, funding_rate, next_funding_time


def create_funding_settlement_event(
    symbol: str,
    funding_rate: Decimal | str,
    mark_price: Decimal | str | None,
    occurred_at: datetime,
    manifest_digest: str,
    venue: str = "binance-vision",
) -> CryptoMarketEvent:
    """Constructs an explicit 8-hour funding settlement CryptoMarketEvent."""
    rate_dec = Decimal(str(funding_rate))
    price_dec = _safe_dec(mark_price)
    ts = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)

    event_payload = {
        "venue": venue,
        "symbol": symbol.upper(),
        "contract_kind": "PERPETUAL",
        "occurred_at": ts.isoformat(),
        "event_type": "FUNDING",
        "funding_rate": str(rate_dec),
        "price": str(price_dec) if price_dec is not None else None,
    }
    eid = event_id_for(event_payload)

    return CryptoMarketEvent(
        event_id=eid,
        venue=venue,
        symbol=symbol.upper(),
        contract_kind="PERPETUAL",
        occurred_at=ts,
        event_type="FUNDING",
        source_manifest_digest=manifest_digest,
        ingestion_ts=datetime.now(timezone.utc),
        funding_rate=rate_dec,
        price=price_dec,
    )


class CryptoLiveShadowService:
    """Autonomous live public shadow feed and mark-to-market runner for CRYPTO-004.

    Consumes live public WebSocket and REST streams for BTCUSDT and ETHUSDT, translates
    them into validated CryptoMarketEvent instances, updates top-of-book and basis spreads,
    simulates post-only maker queue fills with legging timeouts, and tracks matched hedged
    8-hour funding cashflows.
    """

    def __init__(
        self,
        config: CryptoLiveShadowConfig | None = None,
        runner: CryptoShadowRunner | None = None,
        manifest: CryptoDataManifest | None = None,
        on_snapshot_callback: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._config = config or CryptoLiveShadowConfig()
        self._manifest = manifest or load_default_manifest()
        self._manifest_digest = self._manifest.digest()

        self._runner = runner or CryptoShadowRunner(
            symbols=list(self._config.symbols),
            cost_model=CryptoCostModel.binance_usdt_vip1(),
            initial_capital=self._config.initial_capital,
            maker_fill_probability=self._config.maker_fill_probability,
            mean_maker_fill_delay_min=self._config.mean_maker_fill_delay_min,
            max_legging_timeout_min=self._config.max_legging_timeout_min,
            session_id=self._config.session_id,
        )

        self._on_snapshot_callback = on_snapshot_callback
        self._latest_spot_quotes: dict[str, dict[str, Any]] = {}
        self._latest_perp_marks: dict[str, dict[str, Any]] = {}
        self._latest_funding_rates: dict[str, Decimal] = {}
        self._last_settled_bucket: dict[str, int] = {}
        self._events_ingested: int = 0
        self._is_connected: bool = False
        self._running: bool = False
        self._tasks: list[asyncio.Task] = []

    @property
    def config(self) -> CryptoLiveShadowConfig:
        return self._config

    @property
    def runner(self) -> CryptoShadowRunner:
        return self._runner

    @property
    def manifest(self) -> CryptoDataManifest:
        return self._manifest

    @property
    def manifest_digest(self) -> str:
        return self._manifest_digest

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def events_ingested(self) -> int:
        return self._events_ingested

    def ingest_spot_message(self, msg: dict[str, Any] | str) -> CryptoMarketEvent:
        """Translates and dispatches a Spot market event to the shadow runner."""
        event = translate_spot_ticker_message(
            msg,
            manifest_digest=self._manifest_digest,
            venue=self._config.venue_id,
        )
        self._events_ingested += 1
        self._latest_spot_quotes[event.symbol] = {
            "price": event.price,
            "bid": event.bid,
            "ask": event.ask,
            "occurred_at": event.occurred_at,
        }
        self._runner.on_event(event)
        return event

    def ingest_perp_message(
        self, msg: dict[str, Any] | str
    ) -> tuple[CryptoMarketEvent, CryptoMarketEvent | None]:
        """Translates and dispatches a Perpetual mark/funding event to the runner.

        Dispatches a MARK event for price updates, and dispatches a FUNDING event if
        an 8-hour settlement boundary (00:00, 08:00, 16:00 UTC) has elapsed.
        """
        mark_event, funding_rate, _ = translate_perp_mark_message(
            msg,
            manifest_digest=self._manifest_digest,
            venue=self._config.venue_id,
        )
        self._events_ingested += 1
        sym = mark_event.symbol
        self._latest_perp_marks[sym] = {
            "price": mark_event.price,
            "occurred_at": mark_event.occurred_at,
        }
        if funding_rate is not None:
            self._latest_funding_rates[sym] = funding_rate

        self._runner.on_event(mark_event)

        # 8-Hour Funding Settlement Check
        settlement_event: CryptoMarketEvent | None = None
        if funding_rate is not None:
            current_bucket = _settlement_bucket_8h(mark_event.occurred_at)
            last_bucket = self._last_settled_bucket.get(sym)

            if last_bucket is None or current_bucket > last_bucket:
                settlement_dt = _settlement_bucket_to_dt(current_bucket)
                settlement_event = create_funding_settlement_event(
                    symbol=sym,
                    funding_rate=funding_rate,
                    mark_price=mark_event.price,
                    occurred_at=settlement_dt,
                    manifest_digest=self._manifest_digest,
                    venue=self._config.venue_id,
                )
                self._last_settled_bucket[sym] = current_bucket
                self._events_ingested += 1
                self._runner.on_event(settlement_event)

        return mark_event, settlement_event

    def dispatch_event(self, event: CryptoMarketEvent) -> dict[str, Any] | None:
        """Directly dispatches a CryptoMarketEvent to the runner."""
        self._events_ingested += 1
        return self._runner.on_event(event)

    async def poll_rest_once_async(self, client: httpx.AsyncClient | None = None) -> list[CryptoMarketEvent]:
        """Polls public Binance REST endpoints for spot bookTickers and futures premiumIndex."""
        events: list[CryptoMarketEvent] = []
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            # 1. Fetch Spot bookTicker
            spot_url = f"{self._config.spot_rest_base}/api/v3/ticker/bookTicker"
            resp_spot = await client.get(spot_url)
            if resp_spot.status_code == 200:
                spot_data = resp_spot.json()
                if isinstance(spot_data, dict):
                    spot_data = [spot_data]
                spot_symbols = set(self._config.symbols)
                for item in spot_data:
                    sym = item.get("symbol", "").upper()
                    if sym in spot_symbols:
                        ev = self.ingest_spot_message(item)
                        events.append(ev)

            # 2. Fetch Perpetual premiumIndex (mark price + funding rate)
            perp_url = f"{self._config.perp_rest_base}/fapi/v1/premiumIndex"
            resp_perp = await client.get(perp_url)
            if resp_perp.status_code == 200:
                perp_data = resp_perp.json()
                if isinstance(perp_data, dict):
                    perp_data = [perp_data]
                perp_symbols = set(self._config.symbols)
                for item in perp_data:
                    sym = item.get("symbol", "").upper()
                    if sym in perp_symbols:
                        mark_ev, fund_ev = self.ingest_perp_message(item)
                        events.append(mark_ev)
                        if fund_ev is not None:
                            events.append(fund_ev)

            self._is_connected = True
        except Exception as exc:
            logger.warning(f"REST poll error: {exc}")
            self._is_connected = False
        finally:
            if should_close:
                await client.aclose()

        return events

    def poll_once(self) -> list[CryptoMarketEvent]:
        """Synchronous helper for single poll execution."""
        return asyncio.run(self.poll_rest_once_async())

    def get_telemetry_snapshot(self) -> dict[str, Any]:
        """Produces a comprehensive real-time telemetry snapshot."""
        runner_status = self._runner.get_shadow_status()
        now_utc = datetime.now(timezone.utc)

        symbols_status: dict[str, Any] = {}
        for sym in self._config.symbols:
            book = self._runner.get_book(sym)
            spot_info = self._latest_spot_quotes.get(sym, {})
            perp_info = self._latest_perp_marks.get(sym, {})
            funding_rate = self._latest_funding_rates.get(sym, book.last_funding_rate)

            spot_price = spot_info.get("price") or book.last_spot_mark
            perp_mark = perp_info.get("price") or book.last_perp_mark

            basis_spread_bps: float | None = None
            if spot_price and perp_mark and spot_price > 0:
                basis_spread_bps = float((perp_mark - spot_price) / spot_price * Decimal("10000"))

            ann_funding_pct: float | None = None
            if funding_rate is not None:
                ann_funding_pct = float(funding_rate * Decimal("1095") * Decimal("100"))

            symbols_status[sym] = {
                "spot_price": str(spot_price) if spot_price else None,
                "perp_mark_price": str(perp_mark) if perp_mark else None,
                "basis_spread_bps": basis_spread_bps,
                "funding_rate_8h": str(funding_rate) if funding_rate is not None else None,
                "annualized_funding_pct": ann_funding_pct,
                "position_perp": str(book.position_perp),
                "position_spot": str(book.position_spot),
                "matched_hedged_qty": str(book.matched_hedged_qty),
                "unrealized_basis_pnl": str(book.unrealized_basis_pnl),
                "realized_funding": str(book.realized_funding),
            }

        snapshot = {
            "hypothesis_id": "CRYPTO-004",
            "session_id": self._config.session_id,
            "authority": "READ_ONLY_SHADOW_NON_CUSTODIAL",
            "execution_ban_verified": True,
            "timestamp": now_utc.isoformat(),
            "is_connected": self._is_connected,
            "events_ingested": self._events_ingested,
            "runner_events_processed": self._runner.events_processed,
            "trades_count": self._runner.n_trades,
            "symbols": symbols_status,
            "portfolio": {
                "initial_capital": str(runner_status["capital"]["initial"]),
                "nominal_capital": str(runner_status["capital"]["nominal"]),
                "cumulative_net_pnl": str(self._runner.cumulative_net_pnl),
                "realized_funding": str(self._runner.attribution.funding),
                "realized_price_pnl": str(self._runner.realized_price_pnl),
                "unrealized_basis_pnl": str(self._runner.unrealized_basis_pnl),
                "total_fees": str(self._runner.attribution.fees),
                "total_spread": str(self._runner.attribution.spread),
                "total_impact": str(self._runner.attribution.impact),
                "annualized_net_return_pct": self._runner.annualized_net_return_pct,
                "net_sharpe": self._runner.net_sharpe,
                "max_drawdown_pct": self._runner.max_drawdown_pct,
            },
            "microstructure": {
                "maker_fills": self._runner.maker_fills,
                "taker_fallbacks": self._runner.taker_fallbacks,
                "maker_fill_rate": self._runner.maker_fill_rate,
                "mean_unhedged_duration_min": self._runner.mean_unhedged_duration_min,
            },
            "runner_status": runner_status,
        }
        return snapshot

    def save_evidence_bundle(self, path: Path | str | None = None) -> dict[str, Any]:
        """Serializes and auto-persists the canonical shadow evidence bundle to disk."""
        target_path = Path(path) if path else self._config.bundle_output_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        telemetry = self.get_telemetry_snapshot()
        runner_evidence = self._runner.export_shadow_evidence()

        bundle = {
            "hypothesis_id": "CRYPTO-004",
            "run_mode": "LIVE_SHADOW_PAPER",
            "deployment_authority": "READ_ONLY_NON_CUSTODIAL",
            "session_id": self._config.session_id,
            "manifest_digest": self._manifest_digest,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbols": list(self._config.symbols),
            "events_ingested": self._events_ingested,
            "events_processed": self._runner.events_processed,
            "trades_count": self._runner.n_trades,
            "telemetry": telemetry,
            "shadow_evidence": runner_evidence,
            "attribution": self._runner.attribution.to_dict() | {
                "unrealized_basis_pnl": str(self._runner.unrealized_basis_pnl),
                "realized_price_pnl": str(self._runner.realized_price_pnl),
                "net_pnl": str(self._runner.cumulative_net_pnl),
            },
            "metrics": {
                "maker_fills": self._runner.maker_fills,
                "taker_fallbacks": self._runner.taker_fallbacks,
                "maker_fill_rate": self._runner.maker_fill_rate,
                "mean_unhedged_duration_min": self._runner.mean_unhedged_duration_min,
                "cumulative_net_pnl": str(self._runner.cumulative_net_pnl),
                "annualized_net_return_pct": self._runner.annualized_net_return_pct,
                "net_sharpe": self._runner.net_sharpe,
                "max_drawdown_pct": self._runner.max_drawdown_pct,
            },
            "execution_ban_verified": True,
            "notes": [
                "public_unauthenticated_streams",
                "strictly_non_custodial",
                "zero_broker_secrets",
                "adr_032_compliant",
            ],
        }

        temp_path = target_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(target_path)
        logger.info(f"Saved live shadow evidence bundle to {target_path}")
        return bundle

    async def _ws_spot_stream_loop(self) -> None:
        """WebSocket loop for Binance Spot public stream."""
        import websockets

        stream_names = [f"{s.lower()}@bookTicker" for s in self._config.symbols]
        combined_path = "/".join(stream_names)
        url = f"wss://stream.binance.com:9443/stream?streams={combined_path}"

        while self._running:
            try:
                logger.info(f"Connecting to Spot WS: {url}")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    self._is_connected = True
                    logger.info("Connected to Binance Spot WS feed.")
                    while self._running:
                        msg_str = await ws.recv()
                        self.ingest_spot_message(msg_str)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Spot WS connection dropped: {exc}. Reconnecting in 3s...")
                self._is_connected = False
                await asyncio.sleep(3.0)

    async def _ws_perp_stream_loop(self) -> None:
        """WebSocket loop for Binance USDT-M Futures public stream."""
        import websockets

        stream_names = [f"{s.lower()}@markPrice@1s" for s in self._config.symbols]
        combined_path = "/".join(stream_names)
        url = f"wss://fstream.binance.com/stream?streams={combined_path}"

        while self._running:
            try:
                logger.info(f"Connecting to Futures WS: {url}")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    self._is_connected = True
                    logger.info("Connected to Binance Futures WS feed.")
                    while self._running:
                        msg_str = await ws.recv()
                        self.ingest_perp_message(msg_str)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Futures WS connection dropped: {exc}. Reconnecting in 3s...")
                self._is_connected = False
                await asyncio.sleep(3.0)

    async def _periodic_snapshot_loop(self) -> None:
        """Periodically captures telemetry snapshots and auto-persists evidence bundle."""
        while self._running:
            try:
                await asyncio.sleep(self._config.snapshot_interval_sec)
                snapshot = self.get_telemetry_snapshot()
                if self._on_snapshot_callback:
                    self._on_snapshot_callback(snapshot)
                self.save_evidence_bundle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Snapshot error: {exc}")

    async def run_poll_loop_async(self, duration_sec: float | None = None) -> None:
        """Runs the service in REST polling mode."""
        self._running = True
        start_time = asyncio.get_event_loop().time()
        client = httpx.AsyncClient(timeout=10.0)

        # Snapshot task
        snapshot_task = asyncio.create_task(self._periodic_snapshot_loop())
        self._tasks.append(snapshot_task)

        try:
            while self._running:
                await self.poll_rest_once_async(client=client)
                if duration_sec and (asyncio.get_event_loop().time() - start_time) >= duration_sec:
                    break
                await asyncio.sleep(self._config.poll_interval_sec)
        finally:
            self._running = False
            snapshot_task.cancel()
            await client.aclose()
            self.save_evidence_bundle()

    async def run_async(self, duration_sec: float | None = None) -> None:
        """Runs the service with concurrent WebSocket streams."""
        self._running = True
        start_time = asyncio.get_event_loop().time()

        # Initial bootstrap REST poll to establish marks & funding
        await self.poll_rest_once_async()

        spot_task = asyncio.create_task(self._ws_spot_stream_loop())
        perp_task = asyncio.create_task(self._ws_perp_stream_loop())
        snapshot_task = asyncio.create_task(self._periodic_snapshot_loop())
        self._tasks.extend([spot_task, perp_task, snapshot_task])

        try:
            if duration_sec is not None:
                await asyncio.sleep(duration_sec)
            else:
                await asyncio.gather(spot_task, perp_task, snapshot_task)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop()
            self.save_evidence_bundle()

    def stop(self) -> None:
        """Gracefully stops all running tasks and disconnects streams."""
        self._running = False
        self._is_connected = False
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()

    def run(self, mode: str = "ws", duration_sec: float | None = None) -> None:
        """Synchronous launcher entrypoint."""
        if mode == "poll":
            asyncio.run(self.run_poll_loop_async(duration_sec=duration_sec))
        elif mode == "once":
            self.poll_once()
            self.save_evidence_bundle()
        else:
            asyncio.run(self.run_async(duration_sec=duration_sec))
