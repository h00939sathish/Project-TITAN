"""Tests for CRYPTO-003: Order-Flow / Liquidity Imbalance Screen."""

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
from titan.research.crypto_screen_003 import (
    order_flow_imbalance_signal,
    run_crypto_003,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "crypto" / "manifests" / "binance_trades_v1.json"
PREREG_PATH = ROOT / "research" / "crypto" / "hypotheses" / "CRYPTO-003-prereg.json"
SCREEN_003_PY = ROOT / "src" / "titan" / "research" / "crypto_screen_003.py"


def _manifest() -> CryptoDataManifest:
    return CryptoDataManifest.load(MANIFEST_PATH)


def _make_trade_event(
    manifest: CryptoDataManifest,
    event_id: str,
    occurred_at: str,
    sequence: int,
    price: str,
    qty: str,
    side: str,
    symbol: str = "BTCUSDT",
) -> CryptoMarketEvent:
    digest = manifest.digest()
    raw = {
        "event_id": event_id,
        "venue": "binance-vision",
        "symbol": symbol,
        "contract_kind": "PERPETUAL",
        "occurred_at": occurred_at,
        "event_type": "TRADE",
        "sequence": sequence,
        "price": price,
        "qty": qty,
        "side": side,
        "source_manifest_digest": digest,
        "ingestion_ts": "2026-08-16T11:00:00+00:00",
    }
    events = ingest_crypto_snapshot([raw], manifest)
    return events[0]


class TestOrderFlowImbalanceSignal:
    def test_signal_insufficient_history_returns_flat(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "ofi_threshold": "0.40",
                "rolling_window_trades": 5,
            }
        }
        ev1 = _make_trade_event(manifest, "t1", "2025-01-01T00:00:00+00:00", 1, "50000", "1.0", "BUY")
        assert order_flow_imbalance_signal(ev1, state) == Decimal("0")

    def test_signal_buy_imbalance_returns_long(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "ofi_threshold": "0.40",
                "rolling_window_trades": 4,
            }
        }
        # 3 BUYs of 1.0, 1 SELL of 0.2 -> OFI = (3.0 - 0.2) / 3.2 = 2.8 / 3.2 = 0.875 > 0.40 -> BUY (1)
        for i in range(3):
            ev = _make_trade_event(manifest, f"b{i}", f"2025-01-01T00:00:0{i}+00:00", i + 1, "50000", "1.0", "BUY")
            order_flow_imbalance_signal(ev, state)

        ev_last = _make_trade_event(manifest, "s1", "2025-01-01T00:00:04+00:00", 4, "50000", "0.2", "SELL")
        sig = order_flow_imbalance_signal(ev_last, state)
        assert sig == Decimal("1")

    def test_signal_sell_imbalance_returns_short(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "ofi_threshold": "0.40",
                "rolling_window_trades": 4,
            }
        }
        # 3 SELLs of 1.0, 1 BUY of 0.2 -> OFI = (0.2 - 3.0) / 3.2 = -2.8 / 3.2 = -0.875 < -0.40 -> SHORT (-1)
        for i in range(3):
            ev = _make_trade_event(manifest, f"s{i}", f"2025-01-01T00:00:0{i}+00:00", i + 1, "50000", "1.0", "SELL")
            order_flow_imbalance_signal(ev, state)

        ev_last = _make_trade_event(manifest, "b1", "2025-01-01T00:00:04+00:00", 4, "50000", "0.2", "BUY")
        sig = order_flow_imbalance_signal(ev_last, state)
        assert sig == Decimal("-1")

    def test_signal_balanced_flow_returns_flat(self):
        manifest = _manifest()
        state = {
            "parameters": {
                "ofi_threshold": "0.40",
                "rolling_window_trades": 4,
            }
        }
        # 2 BUYs of 1.0, 2 SELLs of 1.0 -> OFI = 0.0 -> FLAT (0)
        for i in range(2):
            ev = _make_trade_event(manifest, f"b{i}", f"2025-01-01T00:00:0{i}+00:00", i + 1, "50000", "1.0", "BUY")
            order_flow_imbalance_signal(ev, state)
        for i in range(2, 4):
            ev = _make_trade_event(manifest, f"s{i}", f"2025-01-01T00:00:0{i}+00:00", i + 1, "50000", "1.0", "SELL")
            sig = order_flow_imbalance_signal(ev, state)
        assert sig == Decimal("0")


class TestCrypto003ScreenEvaluation:
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
            run_crypto_003([], _manifest(), prereg)

    def test_oos_cannot_choose_parameters(self):
        prereg = load_preregistration(PREREG_PATH)
        with pytest.raises(CryptoDataError, match="OOS"):
            run_crypto_003([], _manifest(), prereg, allow_oos_for_parameters=True)

    def test_hypothesis_mismatch_rejected(self):
        prereg = PreRegistration(
            hypothesis_id="CRYPTO-001",
            universe=["BTCUSDT"],
            signal="dummy",
            parameters={"p": 1},
            cost_label="binance_usdt_vip0_2026-08-14",
            is_partition={"from": "2024-08-14T00:00:00+00:00", "to": "2025-01-01T00:00:00+00:00"},
            oos_partition={"from": "2025-01-01T00:00:00+00:00", "to": "2025-06-01T00:00:00+00:00"},
            participation_cap="0.05",
            pass_criteria={"max_concentration": 0.7},
        )
        with pytest.raises(CryptoDataError, match="requires CRYPTO-003"):
            run_crypto_003([], _manifest(), prereg)

    def test_unreplicated_run_evaluates_to_negative_result(self):
        manifest = _manifest()
        prereg = load_preregistration(PREREG_PATH)
        t0 = datetime.fromisoformat(prereg.is_partition["from"].replace("Z", "+00:00"))

        events = []
        # Generate sequence of trade events across IS and OOS
        for i in range(40):
            ts = t0 + timedelta(days=15 * i)
            events.append(
                _make_trade_event(
                    manifest,
                    f"tr_{i}",
                    ts.isoformat(),
                    i + 1,
                    price=str(50000 + (i % 3) * 10),
                    qty="1.0" if i % 2 == 0 else "0.1",
                    side="BUY" if i % 2 == 0 else "SELL",
                )
            )

        events.sort(key=lambda e: (e.occurred_at, e.sequence or 0))
        bundle = run_crypto_003(events, manifest, prereg, replicated=False)

        assert bundle["hypothesis_id"] == "CRYPTO-003"
        assert bundle["gates"]["verdict"] == "negative_result"
        assert bundle["gates"]["gates"]["replication"] is False
        assert (ROOT / "research" / "crypto" / "results" / "CRYPTO-003-evidence-bundle.json").exists()

    def test_crypto_screen_003_cannot_import_execution(self):
        banned_imports = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
        )
        text = SCREEN_003_PY.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"{token} found in {SCREEN_003_PY}"
        assert "import TradeIntent" not in text
        assert "import PaperSession" not in text
