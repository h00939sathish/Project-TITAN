"""Simulator: net PnL parts and exploratory fill label."""

from decimal import Decimal

from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.crypto_simulator import FILL_EXPLORATORY, simulate_crypto

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

from titan.data.crypto import ingest_crypto_snapshot


def test_net_includes_fees_spread_funding_and_exploratory_cannot_qualify():
    manifest = _manifest()
    raws = []
    for i, hour in enumerate((0, 8, 16, 24)):
        day = 1 + hour // 24
        h = hour % 24
        raws.append(
            _funding_raw(
                manifest,
                event_id=f"f{i}",
                occurred_at=f"2025-01-{day:02d}T{h:02d}:00:00+00:00",
                funding_rate="0.01",
                price="10000",
            )
        )
    events = ingest_crypto_snapshot(raws, manifest)
    cost = CryptoCostModel.binance_usdt_vip0()

    def signal(event, state):
        return Decimal("-1")

    art = simulate_crypto(
        events,
        signal,
        cost,
        "IS",
        hypothesis_id="CRYPTO-001",
        parameters={"funding_abs_threshold": "0.0001"},
        data_digest=manifest.digest(),
    )
    attr = art.attribution
    assert attr.fees > 0
    assert attr.spread > 0
    assert attr.impact > 0
    assert attr.funding != 0

    expl = simulate_crypto(
        events,
        signal,
        cost,
        "IS",
        hypothesis_id="CRYPTO-001",
        parameters={"funding_abs_threshold": "0.0001"},
        data_digest=manifest.digest(),
        fill_model=FILL_EXPLORATORY,
    )
    assert expl.can_qualify is False
    assert "cannot qualify" in expl.notes[0]
