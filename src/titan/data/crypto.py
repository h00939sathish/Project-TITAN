"""Read-only crypto market-structure ingestion with provenance.

Research-only. This module must not import execution, broker, paper, or
certificate names. See specifications/CryptoResearch.spec.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from titan.data.calendar_crypto import require_utc

ORDER_FLOW_TYPES = frozenset({"TRADE", "L2_DELTA", "L2_SNAPSHOT"})
CONTRACT_KINDS = frozenset({"SPOT", "PERPETUAL"})
EVENT_TYPES = frozenset({
    "TRADE", "QUOTE", "L2_SNAPSHOT", "L2_DELTA", "FUNDING",
    "OPEN_INTEREST", "MARK", "LIQUIDATION",
})
FORBIDDEN_EXECUTION_NAMES = (
    "TradeIntent",
    "OrderRouter",
    "BrokerAdapter",
    "PaperSession",
    "CertificateIssuer",
)


class CryptoDataError(ValueError):
    """Hard data-quality reject."""


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CryptoDataError(f"invalid decimal: {value!r}") from exc


def _parse_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return require_utc(value)
    if not isinstance(value, str) or not value:
        raise CryptoDataError("occurred_at/ingestion_ts required")
    text = value.replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CryptoDataError(f"invalid timestamp: {value!r}") from exc
    if ts.tzinfo is None:
        raise CryptoDataError("non-UTC timestamp (naive)")
    return require_utc(ts)


def event_id_for(raw: dict[str, Any]) -> str:
    payload = json.dumps(raw, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class CryptoMarketEvent:
    event_id: str
    venue: str
    symbol: str
    contract_kind: str
    occurred_at: datetime
    event_type: str
    source_manifest_digest: str
    ingestion_ts: datetime
    sequence: int | None = None
    price: Decimal | None = None
    qty: Decimal | None = None
    side: str | None = None
    funding_rate: Decimal | None = None
    open_interest: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    bid_qty: Decimal | None = None
    ask_qty: Decimal | None = None
    l2_levels: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "event_id": self.event_id,
            "venue": self.venue,
            "symbol": self.symbol,
            "contract_kind": self.contract_kind,
            "occurred_at": self.occurred_at.isoformat(),
            "sequence": self.sequence,
            "event_type": self.event_type,
            "price": None if self.price is None else str(self.price),
            "qty": None if self.qty is None else str(self.qty),
            "side": self.side,
            "funding_rate": None if self.funding_rate is None else str(self.funding_rate),
            "open_interest": None if self.open_interest is None else str(self.open_interest),
            "bid": None if self.bid is None else str(self.bid),
            "ask": None if self.ask is None else str(self.ask),
            "bid_qty": None if self.bid_qty is None else str(self.bid_qty),
            "ask_qty": None if self.ask_qty is None else str(self.ask_qty),
            "l2_levels": self.l2_levels,
            "source_manifest_digest": self.source_manifest_digest,
            "ingestion_ts": self.ingestion_ts.isoformat(),
        }
        return out


@dataclass
class CryptoDataManifest:
    venue: str
    venue_id: str
    source_url: str
    licence: str
    licence_url: str
    licence_notes: str
    symbols: list[str]
    products: list[dict[str, Any]]
    timezone: str
    timestamp_semantics: str
    coverage_from: str
    coverage_to: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    fee_schedule: dict[str, Any]
    funding_convention: dict[str, Any]
    precision: dict[str, Any]
    retrieval_ts_utc: str
    schema_version: str = "1.0"
    parent_digest: str = ""
    checksums: dict[str, str] = field(default_factory=dict)
    gap_log: list[str] = field(default_factory=list)

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CryptoDataManifest":
        known = {k: data[k] for k in CryptoDataManifest.__dataclass_fields__ if k in data}
        return CryptoDataManifest(**known)

    @staticmethod
    def load(path: str | Path) -> "CryptoDataManifest":
        with open(path, encoding="utf-8") as fh:
            return CryptoDataManifest.from_dict(json.load(fh))


def validate_event_dict(raw: dict[str, Any], *, manifest: CryptoDataManifest) -> CryptoMarketEvent:
    venue = str(raw.get("venue") or "")
    if not venue:
        raise CryptoDataError("missing venue")
    if venue != manifest.venue_id:
        raise CryptoDataError(f"venue {venue!r} not in manifest {manifest.venue_id!r}")

    digest = str(raw.get("source_manifest_digest") or "")
    if not digest:
        raise CryptoDataError("orphan event: missing source_manifest_digest")
    if digest != manifest.digest():
        raise CryptoDataError("orphan event: unresolved manifest digest")

    contract_kind = str(raw.get("contract_kind") or "")
    if contract_kind not in CONTRACT_KINDS:
        raise CryptoDataError("invalid contract_kind")

    event_type = str(raw.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        raise CryptoDataError("invalid event_type")

    symbol = str(raw.get("symbol") or "")
    if not symbol:
        raise CryptoDataError("missing symbol")

    occurred_at = _parse_utc(raw.get("occurred_at"))
    ingestion_ts = _parse_utc(raw.get("ingestion_ts") or datetime.now(timezone.utc).isoformat())

    sequence = raw.get("sequence")
    if event_type in ORDER_FLOW_TYPES and sequence is None:
        raise CryptoDataError("missing sequence on order-flow event")
    if sequence is not None:
        sequence = int(sequence)

    side = raw.get("side")
    if side not in (None, "", "BUY", "SELL"):
        raise CryptoDataError("invalid side")
    if side == "":
        side = None

    event = CryptoMarketEvent(
        event_id=str(raw.get("event_id") or event_id_for(raw)),
        venue=venue,
        symbol=symbol,
        contract_kind=contract_kind,
        occurred_at=occurred_at,
        event_type=event_type,
        source_manifest_digest=digest,
        ingestion_ts=ingestion_ts,
        sequence=sequence,
        price=_dec(raw.get("price")),
        qty=_dec(raw.get("qty")),
        side=side,
        funding_rate=_dec(raw.get("funding_rate")),
        open_interest=_dec(raw.get("open_interest")),
        bid=_dec(raw.get("bid")),
        ask=_dec(raw.get("ask")),
        bid_qty=_dec(raw.get("bid_qty")),
        ask_qty=_dec(raw.get("ask_qty")),
        l2_levels=raw.get("l2_levels"),
    )
    if event.event_type == "FUNDING" and event.funding_rate is None:
        raise CryptoDataError("FUNDING event missing funding_rate")
    if event.event_type == "OPEN_INTEREST" and event.open_interest is None:
        raise CryptoDataError("OPEN_INTEREST event missing open_interest")
    if event.event_type == "TRADE" and (event.price is None or event.qty is None):
        raise CryptoDataError("TRADE event missing price/qty")
    if event.event_type == "QUOTE" and (event.bid is None or event.ask is None):
        raise CryptoDataError("QUOTE event missing bid/ask")
    return event


def ingest_crypto_snapshot(
    raw_events: Iterable[dict[str, Any]],
    manifest: CryptoDataManifest,
) -> list[CryptoMarketEvent]:
    """Normalize and validate a batch. Hard-reject on provenance/UTC/sequence faults."""
    accepted: list[CryptoMarketEvent] = []
    last_ts: dict[tuple[str, str], datetime] = {}
    last_seq: dict[tuple[str, str], int] = {}
    for raw in raw_events:
        event = validate_event_dict(raw, manifest=manifest)
        key = (event.venue, event.symbol)
        prev = last_ts.get(key)
        if prev is not None and event.occurred_at < prev:
            raise CryptoDataError(
                f"occurred_at regression for {key}: {event.occurred_at.isoformat()} < {prev.isoformat()}"
            )
        last_ts[key] = event.occurred_at
        if event.sequence is not None:
            prev_seq = last_seq.get(key)
            if prev_seq is not None and event.sequence <= prev_seq:
                raise CryptoDataError(
                    f"duplicate or decreasing sequence for {key}: {event.sequence} <= {prev_seq}"
                )
            last_seq[key] = event.sequence
        accepted.append(event)
    accepted.sort(key=lambda e: (e.venue, e.symbol, e.occurred_at, e.sequence or 0, e.event_id))
    return accepted


def assert_research_only_source(path: str | Path) -> None:
    text = Path(path).read_text(encoding="utf-8")
    for name in FORBIDDEN_EXECUTION_NAMES:
        if name in text:
            raise CryptoDataError(f"execution name {name} present in {path}")
