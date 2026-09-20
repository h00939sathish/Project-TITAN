"""Tests for CRYPTO-004 Shadow Paper Runner."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from titan.backtest.crypto_costs import CryptoCostModel
from titan.data.crypto import (
    CryptoDataManifest,
    CryptoMarketEvent,
    ingest_crypto_snapshot,
)
from titan.research.crypto_shadow_runner import (
    CryptoShadowRunner,
    ShadowBookState,
    default_maker_carry_signal,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "research" / "crypto" / "manifests" / "binance_vision_v1.json"
SHADOW_RUNNER_PY = ROOT / "src" / "titan" / "research" / "crypto_shadow_runner.py"


def _manifest() -> CryptoDataManifest:
    return CryptoDataManifest.load(MANIFEST_PATH)


def _make_event(
    manifest: CryptoDataManifest,
    event_id: str,
    occurred_at: str,
    event_type: str,
    *,
    symbol: str = "BTCUSDT",
    contract_kind: str = "PERPETUAL",
    funding_rate: str | None = None,
    price: str = "50000",
    qty: str | None = "1.0",
    side: str | None = "BUY",
    sequence: int | None = None,
    bid: str | None = None,
    ask: str | None = None,
) -> CryptoMarketEvent:
    digest = manifest.digest()
    seq = sequence
    if event_type in ("TRADE", "L2_DELTA", "L2_SNAPSHOT") and seq is None:
        seq = 1
    raw = {
        "event_id": event_id,
        "venue": "binance-vision",
        "symbol": symbol,
        "contract_kind": contract_kind,
        "occurred_at": occurred_at,
        "event_type": event_type,
        "sequence": seq,
        "funding_rate": funding_rate,
        "price": price,
        "qty": qty if event_type == "TRADE" else None,
        "side": side if event_type == "TRADE" else None,
        "bid": bid,
        "ask": ask,
        "source_manifest_digest": digest,
        "ingestion_ts": "2026-09-01T08:00:00+00:00",
    }
    events = ingest_crypto_snapshot([raw], manifest)
    return events[0]


class TestExecutionImportBan:
    def test_crypto_shadow_runner_cannot_import_execution(self):
        banned_imports = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
            "import titan.runtime",
            "from titan.portfolio",
            "import titan.portfolio",
        )
        text = SHADOW_RUNNER_PY.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"Banned token {token!r} found in {SHADOW_RUNNER_PY}"

        banned_symbols = (
            "TradeIntent",
            "PaperSession",
            "BrokerAdapter",
            "PaperTradingEngine",
            "CertificateIssuer",
        )
        for sym in banned_symbols:
            assert f"import {sym}" not in text, f"Banned symbol {sym} imported in {SHADOW_RUNNER_PY}"


class TestShadowEventIngestionAndMarks:
    def test_event_ingestion_updates_book_marks(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(symbols=["BTCUSDT", "ETHUSDT"])

        ev_spot = _make_event(
            manifest, "ev1", "2026-09-01T00:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="SPOT", price="50100"
        )
        ev_perp = _make_event(
            manifest, "ev2", "2026-09-01T00:01:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="PERPETUAL", price="50150"
        )

        runner.on_event(ev_spot)
        runner.on_event(ev_perp)

        book = runner.get_book("BTCUSDT")
        assert runner.events_processed == 2
        assert book.last_spot_mark == Decimal("50100")
        assert book.last_perp_mark == Decimal("50150")

        status = runner.get_shadow_status()
        assert status["hypothesis_id"] == "CRYPTO-004"
        assert status["authority"] == "READ_ONLY_SHADOW_NON_CUSTODIAL"
        assert status["execution_ban_verified"] is True
        assert status["events_processed"] == 2


class TestMakerQueueFillSimulation:
    def test_pure_maker_fill_applies_vip1_maker_costs(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )

        ev_entry = _make_event(
            manifest, "f1", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="10000"
        )
        runner.on_event(ev_entry)

        assert runner.maker_fills == 1
        assert runner.taker_fallbacks == 0
        assert runner.maker_fill_rate == 1.0
        assert runner.mean_unhedged_duration_min < 5.0

        # Attribution check: VIP1 Perp maker 1 bps ($1.00) + Spot maker 2 bps ($2.00) = $3.00
        assert runner.attribution.fees == Decimal("3.000000")
        assert runner.attribution.spread == Decimal("0")
        assert runner.attribution.impact == Decimal("0")

        book = runner.get_book("BTCUSDT")
        assert book.position_perp == Decimal("-1")
        assert book.position_spot == Decimal("1")
        assert book.matched_hedged_qty == Decimal("1")


class TestLeggingTimeoutFallback:
    def test_timeout_fallback_applies_taker_friction(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=0.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )

        ev_entry = _make_event(
            manifest, "f1", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="10000"
        )
        runner.on_event(ev_entry)

        assert runner.maker_fills == 0
        assert runner.taker_fallbacks == 1
        assert runner.maker_fill_rate == 0.0
        assert runner.mean_unhedged_duration_min == 15.0

        # Friction check:
        # Perp maker (1 bps = $1.00) + Spot taker (5 bps = $5.00) = $6.00 fee
        # Spot spread (1 bps = $1.00)
        # Spot slippage (0.5 bps = $0.50)
        assert runner.attribution.fees == Decimal("6.000000")
        assert runner.attribution.spread == Decimal("1.0000000")
        assert runner.attribution.impact == Decimal("0.5000000")


class TestMatchedHedgedFundingAccrual:
    def test_funding_cashflow_accrues_on_matched_hedge_only(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )

        # 1. Entry at t0
        ev_t0 = _make_event(
            manifest, "f0", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0004", price="20000"
        )
        runner.on_event(ev_t0)

        book = runner.get_book("BTCUSDT")
        assert book.matched_hedged_qty == Decimal("1")
        # Funding at entry was processed before position opened -> 0 cashflow
        assert runner.attribution.funding == Decimal("0")

        # 2. Settlement at 8 hours (t1 = 08:00 UTC)
        ev_t1 = _make_event(
            manifest, "f1", "2026-09-01T08:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="20000"
        )
        runner.on_event(ev_t1)

        # Expected funding = 1.0 qty * 20000 price * 0.0005 rate = $10.00
        assert runner.attribution.funding == Decimal("10.00000000")
        assert book.realized_funding == Decimal("10.00000000")

    def test_unhedged_position_earns_zero_hedged_funding(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(symbols=["BTCUSDT"])
        book = runner.get_book("BTCUSDT")
        book.position_perp = Decimal("-1")
        book.position_spot = Decimal("0")  # completely unhedged

        ev_fund = _make_event(
            manifest, "f_unhedged", "2026-09-01T08:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="20000"
        )
        runner.on_event(ev_fund)

        # Matched qty is 0, so hedged funding cashflow must be 0
        assert runner.attribution.funding == Decimal("0")


class TestUnrealizedBasisPnL:
    def test_mark_to_market_basis_expansion(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )

        # Enter carry at 50,000
        ev_init = _make_event(
            manifest, "f0", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="50000"
        )
        runner.on_event(ev_init)

        book = runner.get_book("BTCUSDT")
        assert book.spot_entry_price == Decimal("50000")
        assert book.perp_entry_price == Decimal("50000")

        # Basis expands: Spot moves to 50,200 (+200), Perp moves to 50,050 (+50)
        ev_spot = _make_event(
            manifest, "s1", "2026-09-01T01:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="SPOT", price="50200"
        )
        ev_perp = _make_event(
            manifest, "p1", "2026-09-01T01:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="PERPETUAL", price="50050"
        )
        runner.on_event(ev_spot)
        runner.on_event(ev_perp)

        # Spot PnL: +1 * (50200 - 50000) = +$200
        # Perp PnL: -1 * (50050 - 50000) = -$50
        # Basis PnL: +$150
        assert book.unrealized_spot_pnl == Decimal("200")
        assert book.unrealized_perp_pnl == Decimal("-50")
        assert book.unrealized_basis_pnl == Decimal("150")
        assert runner.unrealized_basis_pnl == Decimal("150")


class TestCarryExitAndRealizedPricePnL:
    def test_carry_exit_on_zero_or_negative_funding(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )

        # 1. Enter carry at 50,000
        ev_enter = _make_event(
            manifest, "f0", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="50000"
        )
        runner.on_event(ev_enter)

        # 2. Exit carry at 50,200 spot and 50,100 perp on zero funding
        ev_exit_spot = _make_event(
            manifest, "s_exit", "2026-09-01T08:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="SPOT", price="50200"
        )
        ev_exit_perp = _make_event(
            manifest, "p_exit", "2026-09-01T08:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="PERPETUAL", price="50100"
        )
        runner.on_event(ev_exit_spot)
        runner.on_event(ev_exit_perp)

        ev_exit_fund = _make_event(
            manifest, "f_exit", "2026-09-01T08:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0", price="50100"
        )
        runner.on_event(ev_exit_fund)

        book = runner.get_book("BTCUSDT")
        assert book.position_perp == Decimal("0")
        assert book.position_spot == Decimal("0")
        assert book.matched_hedged_qty == Decimal("0")
        assert runner.unrealized_basis_pnl == Decimal("0")
        assert book.realized_price_pnl > Decimal("0")


class TestMultiSymbolAndEvidenceExport:
    def test_multi_symbol_batch_and_evidence_export(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT", "ETHUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
            session_id="test_shadow_session_001",
        )

        t0 = datetime.fromisoformat("2026-09-01T00:00:00+00:00")
        events = []
        for i in range(5):
            ts = t0 + timedelta(hours=8 * i)
            events.append(_make_event(
                manifest, f"btc_{i}", ts.isoformat(), "FUNDING",
                symbol="BTCUSDT", funding_rate="0.0003", price="50000"
            ))
            events.append(_make_event(
                manifest, f"eth_{i}", ts.isoformat(), "FUNDING",
                symbol="ETHUSDT", funding_rate="0.0004", price="3000"
            ))

        runner.on_events(events)

        evidence = runner.export_shadow_evidence()
        assert evidence["hypothesis_id"] == "CRYPTO-004"
        assert evidence["run_mode"] == "SHADOW_PAPER"
        assert evidence["deployment_authority"] == "READ_ONLY_NON_CUSTODIAL"
        assert evidence["session_id"] == "test_shadow_session_001"
        assert evidence["execution_ban_verified"] is True
        assert "BTCUSDT" in evidence["symbols"]
        assert "ETHUSDT" in evidence["symbols"]
        assert evidence["events_processed"] == 10
        assert "attribution" in evidence
        assert "metrics" in evidence
        assert "positions" in evidence


class TestContinuousMTMBasisTrackingAndDrawdown:
    def test_intraday_basis_shock_captured_in_equity_curve_and_drawdown(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
            initial_capital=Decimal("100000"),
        )

        # 1. Entry at t0 (00:00 UTC) at 50,000 spot & perp
        ev_enter = _make_event(
            manifest, "e1", "2026-09-01T00:00:00+00:00", "FUNDING",
            symbol="BTCUSDT", funding_rate="0.0005", price="50000"
        )
        runner.on_event(ev_enter)

        # 2. Intraday basis shock at 02:00 UTC (No funding event! Spot drops to 48,000 while perp stays at 50,000)
        # Spot leg: +1 * (48000 - 50000) = -$2,000
        # Perp leg: -1 * (50000 - 50000) = $0
        # Total unrealized basis drawdown = -$2,000 on ~$120k nominal capital (~1.67%)
        ev_shock_spot = _make_event(
            manifest, "shock_spot", "2026-09-01T02:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="SPOT", price="48000"
        )
        runner.on_event(ev_shock_spot)

        assert runner.unrealized_basis_pnl == Decimal("-2000")
        assert runner.max_drawdown_pct > 1.0  # Proves continuous MTM catches intraday basis drawdown!

        # 3. Basis recovers at 04:00 UTC before next funding settlement
        ev_recov_spot = _make_event(
            manifest, "recov_spot", "2026-09-01T04:00:00+00:00", "TRADE",
            symbol="BTCUSDT", contract_kind="SPOT", price="50000"
        )
        runner.on_event(ev_recov_spot)

        assert runner.unrealized_basis_pnl == Decimal("0")
        # Drawdown remains preserved from the peak-to-trough intraday excursion
        assert runner.max_drawdown_pct > 1.0

    def test_daily_resampled_sharpe_calculation(self):
        manifest = _manifest()
        runner = CryptoShadowRunner(
            symbols=["BTCUSDT"],
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
            initial_capital=Decimal("100000"),
        )

        # Multi-day events: 5 days of positive funding carry
        t0 = datetime.fromisoformat("2026-09-01T00:00:00+00:00")
        for day in range(5):
            for h in (0, 8, 16):
                ts = t0 + timedelta(days=day, hours=h)
                ev = _make_event(
                    manifest, f"ev_{day}_{h}", ts.isoformat(), "FUNDING",
                    symbol="BTCUSDT", funding_rate="0.0004", price="50000"
                )
                runner.on_event(ev)

        assert len(runner.daily_net_returns) == 4  # 5 daily closes -> 4 daily returns
        assert runner.net_sharpe > 0.0

    def test_unregistered_symbol_dynamic_ingestion(self):
        manifest = _manifest()
        # Runner configured with only BTCUSDT
        runner = CryptoShadowRunner(symbols=["BTCUSDT"])
        # Ingest SOLUSDT event (unregistered at init)
        ev_sol = _make_event(
            manifest, "sol_1", "2026-09-01T00:00:00+00:00", "TRADE",
            symbol="SOLUSDT", contract_kind="SPOT", price="150"
        )
        res = runner.on_event(ev_sol)
        assert res is not None
        assert "SOLUSDT" in runner._books
        assert runner.get_book("SOLUSDT").last_spot_mark == Decimal("150")
