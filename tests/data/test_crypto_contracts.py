"""CryptoMarketEvent contract tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from titan.data.crypto import CryptoDataError, CryptoDataManifest, ingest_crypto_snapshot, validate_event_dict

SCHEMA = Path(__file__).resolve().parents[2] / "contracts" / "crypto-market-event-v1.schema.json"
MANIFEST_PATH = Path(__file__).resolve().parents[2] / "research" / "crypto" / "manifests" / "binance_vision_v1.json"


def _manifest() -> CryptoDataManifest:
    return CryptoDataManifest.load(MANIFEST_PATH)


def _funding_raw(manifest: CryptoDataManifest, **overrides):
    digest = manifest.digest()
    raw = {
        "event_id": "fix-1",
        "venue": "binance-vision",
        "symbol": "BTCUSDT",
        "contract_kind": "PERPETUAL",
        "occurred_at": "2025-01-01T00:00:00+00:00",
        "event_type": "FUNDING",
        "funding_rate": "0.0003",
        "source_manifest_digest": digest,
        "ingestion_ts": "2026-08-14T00:00:00+00:00",
    }
    raw.update(overrides)
    return raw


def test_schema_file_exists_and_requires_core_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for field in (
        "venue",
        "symbol",
        "contract_kind",
        "occurred_at",
        "event_type",
        "source_manifest_digest",
    ):
        assert field in schema["required"]


def test_valid_utc_perpetual_funding_event():
    manifest = _manifest()
    event = validate_event_dict(_funding_raw(manifest), manifest=manifest)
    assert event.event_type == "FUNDING"
    assert event.contract_kind == "PERPETUAL"
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset().total_seconds() == 0
    assert event.funding_rate is not None


def test_missing_venue_rejected():
    manifest = _manifest()
    with pytest.raises(CryptoDataError, match="venue"):
        validate_event_dict(_funding_raw(manifest, venue=""), manifest=manifest)


def test_missing_manifest_digest_rejected():
    manifest = _manifest()
    with pytest.raises(CryptoDataError, match="orphan"):
        validate_event_dict(_funding_raw(manifest, source_manifest_digest=""), manifest=manifest)


def test_trade_missing_sequence_rejected():
    manifest = _manifest()
    raw = _funding_raw(
        manifest,
        event_type="TRADE",
        funding_rate=None,
        price="100",
        qty="1",
        sequence=None,
    )
    with pytest.raises(CryptoDataError, match="sequence"):
        validate_event_dict(raw, manifest=manifest)


def test_ingest_sorts_and_accepts_batch():
    manifest = _manifest()
    events = ingest_crypto_snapshot(
        [
            _funding_raw(manifest, event_id="a", occurred_at="2025-01-01T00:00:00+00:00"),
            _funding_raw(manifest, event_id="b", occurred_at="2025-01-01T08:00:00+00:00"),
        ],
        manifest,
    )
    assert [e.event_id for e in events] == ["a", "b"]
