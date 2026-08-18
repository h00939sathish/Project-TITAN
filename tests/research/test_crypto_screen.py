"""CRYPTO-001 screen gates and research-only boundary."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from titan.research.crypto_screen import PreRegistration, load_preregistration, run_crypto_001
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


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "crypto" / "hypotheses" / "CRYPTO-001-prereg.json"
SRC_ROOT = ROOT / "src" / "titan"
SCREEN_PY = ROOT / "src" / "titan" / "research" / "crypto_screen.py"
COST_PY = ROOT / "src" / "titan" / "backtest" / "crypto_costs.py"
SIM_PY = ROOT / "src" / "titan" / "backtest" / "crypto_simulator.py"
CRYPTO_PY = ROOT / "src" / "titan" / "data" / "crypto.py"


def _events_for(manifest: CryptoDataManifest, start: str, n: int, rate: str, prefix: str):
    t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
    raws = []
    for i in range(n):
        ts = t0 + timedelta(hours=8 * i)
        raws.append(
            _funding_raw(
                manifest,
                event_id=f"{prefix}{i}",
                occurred_at=ts.isoformat(),
                funding_rate=rate,
                price="10000",
                symbol="BTCUSDT",
            )
        )
    return ingest_crypto_snapshot(raws, manifest)


def test_missing_preregistration_fields_rejected():
    prereg = PreRegistration(
        hypothesis_id="",
        universe=[],
        signal="",
        parameters={},
        cost_label="",
        is_partition={},
        oos_partition={},
        participation_cap="",
        pass_criteria={},
    )
    assert prereg.missing_fields()
    with pytest.raises(CryptoDataError, match="missing pre-registration"):
        run_crypto_001([], _manifest(), prereg)


def test_oos_cannot_choose_parameters():
    prereg = load_preregistration(PREREG)
    with pytest.raises(CryptoDataError, match="OOS"):
        run_crypto_001([], _manifest(), prereg, allow_oos_for_parameters=True)


def test_unreplicated_result_is_negative():
    manifest = _manifest()
    prereg = load_preregistration(PREREG)
    is_events = _events_for(manifest, prereg.is_partition["from"], 6, "0.01", "is")
    oos_events = _events_for(manifest, prereg.oos_partition["from"], 6, "0.01", "oos")
    bundle = run_crypto_001(is_events + oos_events, manifest, prereg, replicated=False)
    assert bundle["gates"]["verdict"] == "negative_result"
    assert bundle["gates"]["gates"]["replication"] is False
    assert "fees" in bundle["oos"]["attribution"]
    assert bundle["oos"]["can_qualify"] is True


def test_crypto_package_cannot_create_execution_objects():
    banned_imports = (
        "from titan.execution",
        "import titan.execution",
        "from titan.runtime",
        "from titan.execution",
    )
    for path in (CRYPTO_PY, COST_PY, SIM_PY, SCREEN_PY):
        text = path.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"{token} found in {path}"
        # names may appear in an explicit forbidden tuple; they must not be imported
        assert "import TradeIntent" not in text
        assert "import PaperSession" not in text
