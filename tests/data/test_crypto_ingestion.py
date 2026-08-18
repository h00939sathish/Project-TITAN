"""Ingestion provenance and 24/7 validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from titan.data.calendar_crypto import is_crypto_trading_day
from titan.data.crypto import CryptoDataError, CryptoDataManifest, ingest_crypto_snapshot

from pathlib import Path as _P
from titan.data.crypto import CryptoDataManifest as _CDM
_MANIFEST_PATH = _P(__file__).resolve().parents[2] / "research" / "crypto" / "manifests" / "binance_vision_v1.json"

def _manifest():
    return _CDM.load(_MANIFEST_PATH)

def _funding_raw(manifest, **overrides):
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


from datetime import date


def test_checksum_mismatch_orphan_digest():
    manifest = _manifest()
    raw = _funding_raw(manifest, source_manifest_digest="0" * 64)
    with pytest.raises(CryptoDataError, match="unresolved"):
        ingest_crypto_snapshot([raw], manifest)


def test_non_utc_timestamp_rejected():
    manifest = _manifest()
    with pytest.raises(CryptoDataError):
        ingest_crypto_snapshot(
            [_funding_raw(manifest, occurred_at="2025-01-01T00:00:00")],
            manifest,
        )


def test_occurred_at_regression_rejected():
    manifest = _manifest()
    with pytest.raises(CryptoDataError, match="regression"):
        ingest_crypto_snapshot(
            [
                _funding_raw(manifest, event_id="1", occurred_at="2025-01-01T08:00:00+00:00"),
                _funding_raw(manifest, event_id="2", occurred_at="2025-01-01T00:00:00+00:00"),
            ],
            manifest,
        )


def test_duplicate_sequence_rejected_on_trades():
    manifest = _manifest()
    def trade(seq: int, ts: str, eid: str):
        return {
            **_funding_raw(
                manifest,
                event_id=eid,
                event_type="TRADE",
                funding_rate=None,
                price="100",
                qty="1",
                sequence=seq,
                occurred_at=ts,
            )
        }

    with pytest.raises(CryptoDataError, match="sequence"):
        ingest_crypto_snapshot(
            [
                trade(1, "2025-01-01T00:00:00+00:00", "t1"),
                trade(1, "2025-01-01T00:00:01+00:00", "t2"),
            ],
            manifest,
        )


def test_crypto_calendar_is_24_7():
    assert is_crypto_trading_day(date(2026, 1, 1)) is True
    assert is_crypto_trading_day(date(2026, 12, 25)) is True
