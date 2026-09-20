"""Tests for Live Public WebSocket Shadow Feed and Runner (CRYPTO-004)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from titan.data.crypto import CryptoDataManifest, CryptoMarketEvent
from titan.research.crypto_shadow_live import (
    CryptoLiveShadowConfig,
    CryptoLiveShadowService,
    create_funding_settlement_event,
    load_default_manifest,
    translate_perp_mark_message,
    translate_spot_ticker_message,
)
from titan.research.crypto_shadow_runner import CryptoShadowRunner

ROOT = Path(__file__).resolve().parents[2]
SHADOW_LIVE_PY = ROOT / "src" / "titan" / "research" / "crypto_shadow_live.py"
RUN_SHADOW_PY = ROOT / "scripts" / "run_crypto_shadow.py"


class TestLiveShadowExecutionImportBan:
    """Enforces strict ADR-032 import ban on execution and runtime engines."""

    def test_crypto_shadow_live_cannot_import_execution(self):
        banned_tokens = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
            "import titan.runtime",
            "from titan.portfolio",
            "import titan.portfolio",
            "BrokerAdapter",
            "PaperSession",
            "PaperTradingEngine",
            "TradeIntent",
            "CertificateIssuer",
        )
        for path in (SHADOW_LIVE_PY, RUN_SHADOW_PY):
            text = path.read_text(encoding="utf-8")
            for token in banned_tokens:
                assert token not in text, f"Banned token {token!r} found in {path}"


class TestMessageTranslation:
    """Tests parsing and translating Binance public WebSocket / REST payloads."""

    def test_translate_spot_book_ticker(self):
        manifest = load_default_manifest()
        digest = manifest.digest()

        raw_book_ticker = {
            "u": 400900217,
            "s": "BTCUSDT",
            "b": "50000.00",
            "B": "1.500",
            "a": "50002.00",
            "A": "2.100",
            "E": 1700000000000,
        }
        event = translate_spot_ticker_message(raw_book_ticker, manifest_digest=digest)

        assert event.symbol == "BTCUSDT"
        assert event.contract_kind == "SPOT"
        assert event.event_type == "QUOTE"
        assert event.bid == Decimal("50000.00")
        assert event.ask == Decimal("50002.00")
        assert event.price == Decimal("50001.00")  # mid price
        assert event.bid_qty == Decimal("1.500")
        assert event.ask_qty == Decimal("2.100")
        assert event.source_manifest_digest == digest

    def test_translate_spot_trade(self):
        manifest = load_default_manifest()
        digest = manifest.digest()

        raw_trade = {
            "e": "trade",
            "E": 1700000000000,
            "s": "ETHUSDT",
            "t": 123456,
            "p": "3000.50",
            "q": "0.50",
            "b": 88,
            "a": 50,
            "T": 1700000000000,
            "m": True,  # buyer is maker -> SELL
        }
        event = translate_spot_ticker_message(raw_trade, manifest_digest=digest)

        assert event.symbol == "ETHUSDT"
        assert event.contract_kind == "SPOT"
        assert event.event_type == "TRADE"
        assert event.price == Decimal("3000.50")
        assert event.qty == Decimal("0.50")
        assert event.side == "SELL"
        assert event.sequence == 123456

    def test_translate_wrapped_stream_payload(self):
        manifest = load_default_manifest()
        digest = manifest.digest()

        wrapped = {
            "stream": "btcusdt@bookTicker",
            "data": {
                "s": "BTCUSDT",
                "b": "51000.00",
                "a": "51001.00",
                "E": 1700000000000,
            },
        }
        event = translate_spot_ticker_message(wrapped, manifest_digest=digest)
        assert event.symbol == "BTCUSDT"
        assert event.bid == Decimal("51000.00")
        assert event.ask == Decimal("51001.00")

    def test_translate_perp_mark_price_and_funding(self):
        manifest = load_default_manifest()
        digest = manifest.digest()

        raw_mark = {
            "e": "markPriceUpdate",
            "E": 1700000000000,
            "s": "BTCUSDT",
            "p": "50050.00000000",
            "i": "50045.00000000",
            "r": "0.00010000",
            "T": 1700028800000,
        }
        event, funding_rate, next_funding = translate_perp_mark_message(raw_mark, manifest_digest=digest)

        assert event.symbol == "BTCUSDT"
        assert event.contract_kind == "PERPETUAL"
        assert event.event_type == "MARK"
        assert event.price == Decimal("50050.00000000")
        assert funding_rate == Decimal("0.00010000")
        assert next_funding == 1700028800000

    def test_create_funding_settlement_event(self):
        manifest = load_default_manifest()
        digest = manifest.digest()

        dt = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)
        ev = create_funding_settlement_event(
            symbol="BTCUSDT",
            funding_rate=Decimal("0.0002"),
            mark_price=Decimal("50000"),
            occurred_at=dt,
            manifest_digest=digest,
        )
        assert ev.symbol == "BTCUSDT"
        assert ev.contract_kind == "PERPETUAL"
        assert ev.event_type == "FUNDING"
        assert ev.funding_rate == Decimal("0.0002")
        assert ev.price == Decimal("50000")
        assert ev.occurred_at == dt


class TestFundingSettlementCadence:
    """Verifies that 8-hour funding rate events trigger settlement strictly on 8h boundaries."""

    def test_8h_boundary_settlement_dispatch(self):
        config = CryptoLiveShadowConfig(symbols=("BTCUSDT",))
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            parameters={"funding_abs_threshold": "0.00001"},
            maker_fill_probability=1.0,
        )
        service = CryptoLiveShadowService(config=config, runner=runner)

        # 1. First event at 00:00 UTC -> triggers initial 8h funding settlement & carry entry
        mark_msg_1 = {
            "e": "markPriceUpdate",
            "E": int(datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
            "s": "BTCUSDT",
            "p": "50000.00",
            "r": "0.00050000",
        }
        mark_ev_1, fund_ev_1 = service.ingest_perp_message(mark_msg_1)
        assert fund_ev_1 is not None
        assert fund_ev_1.event_type == "FUNDING"
        assert fund_ev_1.funding_rate == Decimal("0.00050000")

        # Ingest spot event to complete hedge
        spot_msg_1 = {
            "s": "BTCUSDT",
            "b": "50000.00",
            "a": "50001.00",
            "E": int(datetime(2026, 9, 1, 0, 0, 1, tzinfo=timezone.utc).timestamp() * 1000),
        }
        service.ingest_spot_message(spot_msg_1)

        book = runner.get_book("BTCUSDT")
        assert book.position_perp == Decimal("-1")
        assert book.position_spot == Decimal("1")
        assert book.matched_hedged_qty == Decimal("1")

        # 2. Subsequent mark messages in the same 8-hour bucket (e.g. 02:00 UTC) DO NOT duplicate settlement
        mark_msg_2 = {
            "e": "markPriceUpdate",
            "E": int(datetime(2026, 9, 1, 2, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
            "s": "BTCUSDT",
            "p": "50100.00",
            "r": "0.00050000",
        }
        mark_ev_2, fund_ev_2 = service.ingest_perp_message(mark_msg_2)
        assert fund_ev_2 is None  # no settlement duplicate
        assert runner.attribution.funding == Decimal("0")  # no extra funding yet

        # 3. Next 8-hour boundary at 08:00 UTC triggers settlement on matched hedged notional
        mark_msg_3 = {
            "e": "markPriceUpdate",
            "E": int(datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
            "s": "BTCUSDT",
            "p": "50200.00",
            "r": "0.00040000",
        }
        mark_ev_3, fund_ev_3 = service.ingest_perp_message(mark_msg_3)
        assert fund_ev_3 is not None
        assert fund_ev_3.event_type == "FUNDING"

        # Expected funding = 1.0 hedged qty * 50200 perp mark * 0.0004 rate = $20.08
        expected_funding = Decimal("1.0") * Decimal("50200.00") * Decimal("0.00040000")
        assert runner.attribution.funding == expected_funding
        assert book.realized_funding == expected_funding


class TestMockStreamIngestionAndTelemetry:
    """Verifies live feed processing and snapshot telemetry integrity."""

    def test_telemetry_snapshot_metrics(self):
        config = CryptoLiveShadowConfig(symbols=("BTCUSDT", "ETHUSDT"))
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT", "ETHUSDT"],
            parameters={"funding_abs_threshold": "0.00001"},
            maker_fill_probability=1.0,
        )
        service = CryptoLiveShadowService(config=config, runner=runner)

        # Ingest Spot BTC = $50,000, ETH = $3,000
        service.ingest_spot_message({"s": "BTCUSDT", "b": "50000.00", "a": "50002.00", "E": 1700000000000})
        service.ingest_spot_message({"s": "ETHUSDT", "b": "3000.00", "a": "3001.00", "E": 1700000000000})

        # Ingest Perp BTC = $50,050 (spread +10 bps), ETH = $3,003 (spread +10 bps)
        service.ingest_perp_message({"s": "BTCUSDT", "p": "50050.00", "r": "0.00010000", "E": 1700000000000})
        service.ingest_perp_message({"s": "ETHUSDT", "p": "3003.00", "r": "0.00015000", "E": 1700000000000})

        snapshot = service.get_telemetry_snapshot()

        assert snapshot["hypothesis_id"] == "CRYPTO-004"
        assert snapshot["authority"] == "READ_ONLY_SHADOW_NON_CUSTODIAL"
        assert snapshot["execution_ban_verified"] is True
        assert snapshot["events_ingested"] >= 4

        btc_data = snapshot["symbols"]["BTCUSDT"]
        assert btc_data["spot_price"] == "50001.00"
        assert btc_data["perp_mark_price"] == "50050.00"
        assert btc_data["basis_spread_bps"] == pytest.approx(9.8, abs=0.1)
        assert btc_data["funding_rate_8h"] == "0.00010000"
        assert btc_data["annualized_funding_pct"] == pytest.approx(10.95, abs=0.1)

        eth_data = snapshot["symbols"]["ETHUSDT"]
        assert eth_data["spot_price"] == "3000.50"
        assert eth_data["perp_mark_price"] == "3003.00"
        assert eth_data["basis_spread_bps"] == pytest.approx(8.3, abs=0.1)
        assert eth_data["funding_rate_8h"] == "0.00015000"
        assert eth_data["annualized_funding_pct"] == pytest.approx(16.425, abs=0.1)

        # Portfolio metrics check
        assert "portfolio" in snapshot
        assert "microstructure" in snapshot
        assert snapshot["microstructure"]["maker_fill_rate"] == 1.0


class TestEvidenceBundlePersistence:
    """Verifies atomic evidence export for CRYPTO-004 governance review."""

    def test_save_evidence_bundle_creates_valid_json(self, tmp_path):
        bundle_file = tmp_path / "CRYPTO-004-live-shadow-bundle.json"
        config = CryptoLiveShadowConfig(
            symbols=("BTCUSDT",),
            bundle_output_path=bundle_file,
        )
        service = CryptoLiveShadowService(config=config)

        # Ingest a mock event
        service.ingest_spot_message({"s": "BTCUSDT", "b": "60000.00", "a": "60001.00", "E": 1700000000000})
        service.ingest_perp_message({"s": "BTCUSDT", "p": "60020.00", "r": "0.00020000", "E": 1700000000000})

        bundle = service.save_evidence_bundle(bundle_file)

        assert bundle_file.exists()
        loaded = json.loads(bundle_file.read_text(encoding="utf-8"))

        assert loaded["hypothesis_id"] == "CRYPTO-004"
        assert loaded["run_mode"] == "LIVE_SHADOW_PAPER"
        assert loaded["deployment_authority"] == "READ_ONLY_NON_CUSTODIAL"
        assert loaded["execution_ban_verified"] is True
        assert loaded["events_ingested"] >= 2
        assert "telemetry" in loaded
        assert "shadow_evidence" in loaded
        assert "attribution" in loaded
        assert "metrics" in loaded


class TestRestPollMock:
    """Verifies REST polling fallback with mock responses."""

    @pytest.mark.asyncio
    async def test_poll_rest_once_async_mock(self):
        config = CryptoLiveShadowConfig(symbols=("BTCUSDT", "ETHUSDT"))
        service = CryptoLiveShadowService(config=config)

        mock_spot_resp = MagicMock()
        mock_spot_resp.status_code = 200
        mock_spot_resp.json.return_value = [
            {"symbol": "BTCUSDT", "bidPrice": "50000.00", "bidQty": "1.0", "askPrice": "50001.00", "askQty": "1.0"},
            {"symbol": "ETHUSDT", "bidPrice": "3000.00", "bidQty": "5.0", "askPrice": "3001.00", "askQty": "5.0"},
        ]

        mock_perp_resp = MagicMock()
        mock_perp_resp.status_code = 200
        mock_perp_resp.json.return_value = [
            {"symbol": "BTCUSDT", "markPrice": "50050.00", "lastFundingRate": "0.00010000", "time": 1700000000000},
            {"symbol": "ETHUSDT", "markPrice": "3003.00", "lastFundingRate": "0.00015000", "time": 1700000000000},
        ]

        client = AsyncMock()

        async def mock_get(url):
            if "bookTicker" in url:
                return mock_spot_resp
            elif "premiumIndex" in url:
                return mock_perp_resp
            raise ValueError(f"Unexpected url {url}")

        client.get.side_effect = mock_get

        events = await service.poll_rest_once_async(client=client)

        assert len(events) >= 4
        assert service.is_connected is True
        assert "BTCUSDT" in service._latest_spot_quotes
        assert "ETHUSDT" in service._latest_perp_marks


class TestZeroCredentialsInvariant:
    """Verifies that no credentials or secret keys exist in config or state."""

    def test_config_contains_zero_secrets(self):
        config = CryptoLiveShadowConfig()
        config_dict = config.__dict__
        for k in config_dict:
            assert "key" not in k.lower() or k == "bundle_output_path"
            assert "secret" not in k.lower()
            assert "password" not in k.lower()
            assert "token" not in k.lower()
            assert "auth" not in k.lower()

        service = CryptoLiveShadowService(config=config)
        assert service.config.spot_ws_base.startswith("wss://")
        assert service.config.perp_ws_base.startswith("wss://")
        assert "apiKey" not in service.config.spot_ws_base
