"""Tests for CRYPTO-002: Funding + Open-Interest Deleveraging Screen."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from titan.data.crypto import (
    CryptoDataError,
    CryptoDataManifest,
    CryptoMarketEvent,
    ingest_crypto_snapshot,
)
from titan.research.crypto_screen import (
    PreRegistration,
    load_preregistration,
)
from titan.research.crypto_screen_002 import (
    funding_oi_deleveraging_signal,
    run_crypto_002,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "crypto" / "manifests" / "binance_oi_v1.json"
PREREG_PATH = ROOT / "research" / "crypto" / "hypotheses" / "CRYPTO-002-prereg.json"
SCREEN_002_PY = ROOT / "src" / "titan" / "research" / "crypto_screen_002.py"


def _manifest() -> CryptoDataManifest:
    return CryptoDataManifest.load(MANIFEST_PATH)


def _make_event(
    manifest: CryptoDataManifest,
    event_id: str,
    event_type: str,
    occurred_at: str,
    *,
    funding_rate: str | None = None,
    open_interest: str | None = None,
    price: str | None = None,
    symbol: str = "BTCUSDT",
) -> CryptoMarketEvent:
    digest = manifest.digest()
    raw = {
        "event_id": event_id,
        "venue": "binance-vision",
        "symbol": symbol,
        "contract_kind": "PERPETUAL",
        "occurred_at": occurred_at,
        "event_type": event_type,
        "source_manifest_digest": digest,
        "ingestion_ts": "2026-08-16T11:00:00+00:00",
    }
    if funding_rate is not None:
        raw["funding_rate"] = funding_rate
    if open_interest is not None:
        raw["open_interest"] = open_interest
    if price is not None:
        raw["price"] = price
    events = ingest_crypto_snapshot([raw], manifest)
    return events[0]


class TestFundingOIDeleveragingSignal:
    def test_signal_insufficient_history_returns_flat(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "funding_abs_threshold": "0.0003",
                "oi_change_threshold_pct": "0.03",
                "oi_lookback_intervals": 5,
            }
        }
        ev1 = _make_event(manifest, "f1", "FUNDING", "2025-01-01T00:00:00+00:00", funding_rate="0.0005")
        assert funding_oi_deleveraging_signal(ev1, state) == Decimal("0")

        # Add 2 OI events (less than lookback 5)
        ev2 = _make_event(manifest, "oi1", "OPEN_INTEREST", "2025-01-01T01:00:00+00:00", open_interest="1000")
        assert funding_oi_deleveraging_signal(ev2, state) == Decimal("0")

    def test_signal_crowded_long_buildup_returns_short(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "funding_abs_threshold": "0.0003",
                "oi_change_threshold_pct": "0.03",
                "oi_lookback_intervals": 3,
            }
        }
        # Extreme positive funding
        _make_event(manifest, "f1", "FUNDING", "2025-01-01T00:00:00+00:00", funding_rate="0.0005")
        funding_oi_deleveraging_signal(
            _make_event(manifest, "f1", "FUNDING", "2025-01-01T00:00:00+00:00", funding_rate="0.0005"), state
        )

        # OI increasing by 10% (1000 -> 1050 -> 1100)
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi1", "OPEN_INTEREST", "2025-01-01T01:00:00+00:00", open_interest="1000"), state
        )
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi2", "OPEN_INTEREST", "2025-01-01T02:00:00+00:00", open_interest="1050"), state
        )
        ev3 = _make_event(manifest, "oi3", "OPEN_INTEREST", "2025-01-01T03:00:00+00:00", open_interest="1100")
        sig = funding_oi_deleveraging_signal(ev3, state)
        assert sig == Decimal("-1")  # Crowded long fade -> SHORT

    def test_signal_long_liquidation_flush_returns_buy(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "funding_abs_threshold": "0.0003",
                "oi_change_threshold_pct": "0.03",
                "oi_lookback_intervals": 3,
            }
        }
        # Extreme positive funding
        funding_oi_deleveraging_signal(
            _make_event(manifest, "f1", "FUNDING", "2025-01-01T00:00:00+00:00", funding_rate="0.0005"), state
        )

        # OI decreasing by 10% (1000 -> 950 -> 900)
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi1", "OPEN_INTEREST", "2025-01-01T01:00:00+00:00", open_interest="1000"), state
        )
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi2", "OPEN_INTEREST", "2025-01-01T02:00:00+00:00", open_interest="950"), state
        )
        ev3 = _make_event(manifest, "oi3", "OPEN_INTEREST", "2025-01-01T03:00:00+00:00", open_interest="900")
        sig = funding_oi_deleveraging_signal(ev3, state)
        assert sig == Decimal("1")  # Liquidation flush exhaust -> BUY

    def test_signal_short_squeeze_flush_returns_short(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "funding_abs_threshold": "0.0003",
                "oi_change_threshold_pct": "0.03",
                "oi_lookback_intervals": 3,
            }
        }
        # Extreme negative funding
        funding_oi_deleveraging_signal(
            _make_event(manifest, "f1", "FUNDING", "2025-01-01T00:00:00+00:00", funding_rate="-0.0005"), state
        )

        # OI decreasing by 10% (1000 -> 950 -> 900)
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi1", "OPEN_INTEREST", "2025-01-01T01:00:00+00:00", open_interest="1000"), state
        )
        funding_oi_deleveraging_signal(
            _make_event(manifest, "oi2", "OPEN_INTEREST", "2025-01-01T02:00:00+00:00", open_interest="950"), state
        )
        ev3 = _make_event(manifest, "oi3", "OPEN_INTEREST", "2025-01-01T03:00:00+00:00", open_interest="900")
        sig = funding_oi_deleveraging_signal(ev3, state)
        assert sig == Decimal("-1")  # Short squeeze exhaust -> SHORT


class TestCrypto002ScreenEvaluation:
    def test_missing_preregistration_fields_rejected(self):
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
        with pytest.raises(CryptoDataError, match="missing pre-registration"):
            run_crypto_002([], _manifest(), prereg)

    def test_oos_cannot_choose_parameters(self):
        prereg = load_preregistration(PREREG_PATH)
        with pytest.raises(CryptoDataError, match="OOS"):
            run_crypto_002([], _manifest(), prereg, allow_oos_for_parameters=True)

    def test_hypothesis_mismatch_rejected(self):
        prereg = PreRegistration(
            hypothesis_id="CRYPTO-001",
            universe=["BTCUSDT"],
            signal="dummy",
            parameters={"p": 1},
            cost_label="binance_usdt_vip0_2026-08-14",
            is_partition={"from": "2024-08-14T00:00:00+00:00", "to": "2025-01-01T00:00:00+00:00"},
            oos_partition={"from": "2025-01-01T00:00:00+00:00", "to": "2025-06-01T00:00:00+00:00"},
            participation_cap="1",
            pass_criteria={"max_concentration": 0.7},
        )
        with pytest.raises(CryptoDataError, match="requires CRYPTO-002"):
            run_crypto_002([], _manifest(), prereg)

    def test_unreplicated_run_evaluates_to_negative_result(self):
        manifest = _manifest()
        prereg = load_preregistration(PREREG_PATH)
        t0 = datetime.fromisoformat(prereg.is_partition["from"].replace("Z", "+00:00"))

        events = []
        # Generate sequence of funding, OI, and price events across IS and OOS
        for i in range(30):
            ts = t0 + timedelta(days=20 * i)
            # Funding event
            events.append(
                _make_event(
                    manifest,
                    f"f_{i}",
                    "FUNDING",
                    ts.isoformat(),
                    funding_rate="0.0005" if i % 2 == 0 else "-0.0005",
                    price="50000",
                )
            )
            # OI event
            events.append(
                _make_event(
                    manifest,
                    f"oi_{i}",
                    "OPEN_INTEREST",
                    (ts + timedelta(minutes=5)).isoformat(),
                    open_interest=str(1000 + (i % 5) * 50),
                    price="50000",
                )
            )

        events.sort(key=lambda e: e.occurred_at)
        bundle = run_crypto_002(events, manifest, prereg, replicated=False)

        assert bundle["hypothesis_id"] == "CRYPTO-002"
        assert bundle["gates"]["verdict"] == "negative_result"
        assert bundle["gates"]["gates"]["replication"] is False
        assert (ROOT / "research" / "crypto" / "results" / "CRYPTO-002-evidence-bundle.json").exists()

    def test_crypto_screen_002_cannot_import_execution(self):
        banned_imports = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
        )
        text = SCREEN_002_PY.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"{token} found in {SCREEN_002_PY}"
        assert "import TradeIntent" not in text
        assert "import PaperSession" not in text
