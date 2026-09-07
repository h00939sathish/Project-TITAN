"""Tests for CRYPTO-004: Maker-Oriented Basis & Funding Rate Carry Screen."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.crypto_simulator import Attribution, CryptoEvidenceArtifact
from titan.data.crypto import (
    CryptoDataError,
    CryptoDataManifest,
    CryptoMarketEvent,
    ingest_crypto_snapshot,
)
from titan.research.crypto_screen_004 import (
    PreRegistration004,
    evaluate_crypto_004_gates,
    load_preregistration_004,
    maker_carry_signal,
    run_crypto_004,
    simulate_crypto_maker_carry,
    simulate_crypto_taker_carry,
)

ROOT = Path(__file__).resolve().parents[2]
PREREG_PATH = ROOT / "research" / "crypto" / "hypotheses" / "CRYPTO-004-prereg.json"
MANIFEST_PATH = ROOT / "research" / "crypto" / "manifests" / "binance_vision_v1.json"
SCREEN_004_PY = ROOT / "src" / "titan" / "research" / "crypto_screen_004.py"


def _manifest() -> CryptoDataManifest:
    return CryptoDataManifest.load(MANIFEST_PATH)


def _make_funding_event(
    manifest: CryptoDataManifest,
    event_id: str,
    occurred_at: str,
    funding_rate: str,
    *,
    price: str = "50000",
    symbol: str = "BTCUSDT",
) -> CryptoMarketEvent:
    digest = manifest.digest()
    raw = {
        "event_id": event_id,
        "venue": "binance-vision",
        "symbol": symbol,
        "contract_kind": "PERPETUAL",
        "occurred_at": occurred_at,
        "event_type": "FUNDING",
        "funding_rate": funding_rate,
        "price": price,
        "source_manifest_digest": digest,
        "ingestion_ts": "2026-08-14T08:35:00+00:00",
    }
    events = ingest_crypto_snapshot([raw], manifest)
    return events[0]


class TestPreRegistrationValidation:
    def test_missing_preregistration_fields_rejected(self):
        prereg = PreRegistration004(
            hypothesis_id="",
            name="",
            asset_class="",
            instruments=[],
            economic_rationale="",
            execution_microstructure_model={},
            cost_schedule={},
            partitions={},
            control_baselines={},
            decision_gates={},
        )
        assert len(prereg.missing_fields()) > 0
        with pytest.raises(CryptoDataError, match="missing pre-registration"):
            run_crypto_004([], _manifest(), prereg)

    def test_oos_cannot_choose_parameters(self):
        prereg = load_preregistration_004(PREREG_PATH)
        with pytest.raises(CryptoDataError, match="OOS"):
            run_crypto_004([], _manifest(), prereg, allow_oos_for_parameters=True)

    def test_hypothesis_mismatch_rejected(self):
        prereg = PreRegistration004(
            hypothesis_id="CRYPTO-001",
            name="wrong_id",
            asset_class="CRYPTO_DERIVATIVES",
            instruments=["BTCUSDT"],
            economic_rationale="test",
            execution_microstructure_model={"entry_structure": "test"},
            cost_schedule={"venue": "BINANCE"},
            partitions={
                "is_partition": {"from": "2024-08-01", "to": "2025-07-31"},
                "oos_partition": {"from": "2025-08-01", "to": "2026-07-31"},
            },
            control_baselines={"control": "test"},
            decision_gates={"gate_1": "test"},
        )
        with pytest.raises(CryptoDataError, match="requires CRYPTO-004"):
            run_crypto_004([], _manifest(), prereg)


class TestMakerCarrySignal:
    def test_positive_funding_above_threshold_returns_short_perp(self):
        manifest = _manifest()
        state = {"parameters": {"funding_abs_threshold": "0.0001"}}
        ev = _make_funding_event(manifest, "f1", "2024-08-01T00:00:00+00:00", "0.0003")
        sig = maker_carry_signal(ev, state)
        assert sig == Decimal("-1")

    def test_zero_or_negative_funding_exits_carry(self):
        manifest = _manifest()
        state = {"parameters": {"funding_abs_threshold": "0.0001"}, "position_perp": Decimal("-1")}
        ev_zero = _make_funding_event(manifest, "f2", "2024-08-01T08:00:00+00:00", "0.0")
        assert maker_carry_signal(ev_zero, state) == Decimal("0")

        ev_neg = _make_funding_event(manifest, "f3", "2024-08-01T16:00:00+00:00", "-0.0002")
        assert maker_carry_signal(ev_neg, state) == Decimal("0")


class TestMakerExecutionAndTimeoutFallback:
    def test_maker_fill_applies_maker_fees_and_zero_spread(self):
        manifest = _manifest()
        cost = CryptoCostModel.binance_usdt_vip1()
        events = [
            _make_funding_event(manifest, "f1", "2024-08-01T00:00:00+00:00", "0.0005", price="10000"),
            _make_funding_event(manifest, "f2", "2024-08-01T08:00:00+00:00", "0.0005", price="10000"),
        ]
        # Force 100% maker fill rate
        art = simulate_crypto_maker_carry(
            events,
            maker_carry_signal,
            cost,
            "IS",
            maker_fill_probability=1.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )
        assert art.extra["maker_fill_rate"] == 1.0
        assert art.extra["taker_fallbacks"] == 0
        assert art.extra["mean_unhedged_duration_min"] < 5.0
        # Spread and slippage should be zero for pure maker fills
        assert art.attribution.spread == Decimal("0")
        assert art.attribution.impact == Decimal("0")
        # Fees: Perp maker 1 bps ($1.00) + Spot maker 2 bps ($2.00) = $3.00
        assert art.attribution.fees == Decimal("3.000000")

    def test_timeout_fallback_triggers_taker_hedge_costs(self):
        manifest = _manifest()
        cost = CryptoCostModel.binance_usdt_vip1()
        events = [
            _make_funding_event(manifest, "f1", "2024-08-01T00:00:00+00:00", "0.0005", price="10000"),
            _make_funding_event(manifest, "f2", "2024-08-01T08:00:00+00:00", "0.0005", price="10000"),
        ]
        # Force 0% maker fill rate (all fallback to taker at 15m)
        art = simulate_crypto_maker_carry(
            events,
            maker_carry_signal,
            cost,
            "IS",
            maker_fill_probability=0.0,
            parameters={"funding_abs_threshold": "0.0001"},
        )
        assert art.extra["maker_fill_rate"] == 0.0
        assert art.extra["taker_fallbacks"] == 1
        assert art.extra["mean_unhedged_duration_min"] == 15.0
        # Spread (1.0 bps on spot = $1.00) and slippage (0.5 bps on spot = $0.50)
        assert art.attribution.spread == Decimal("1.0000000")
        assert art.attribution.impact == Decimal("0.5000000")
        # Fees: Perp maker 1 bps ($1.00) + Spot taker 5 bps ($5.00) = $6.00
        assert art.attribution.fees == Decimal("6.000000")


class TestMatchedHedgedFundingSettlement:
    def test_funding_cashflow_earned_only_on_matched_hedge(self):
        manifest = _manifest()
        cost = CryptoCostModel.binance_usdt_vip1()
        events = [
            _make_funding_event(manifest, "f1", "2024-08-01T00:00:00+00:00", "0.001", price="10000"),
            _make_funding_event(manifest, "f2", "2024-08-01T08:00:00+00:00", "0.001", price="10000"),
        ]
        art = simulate_crypto_maker_carry(
            events,
            maker_carry_signal,
            cost,
            "IS",
            parameters={"funding_abs_threshold": "0.0001"},
        )
        # Position was opened on f1, so at f2 (8h settlement) matched hedged notional = $10,000
        # Funding rate = 0.001 -> Funding received = $10,000 * 0.001 = $10.00
        assert art.attribution.funding == Decimal("10.00000000")


class TestDecisionGateEvaluation:
    def test_all_gates_passing_evaluates_to_candidate(self):
        prereg = load_preregistration_004(PREREG_PATH)
        oos_art = CryptoEvidenceArtifact(
            hypothesis_id="CRYPTO-004",
            fill_model="maker_post_only_with_15m_taker_fallback",
            can_qualify=True,
            partition="OOS",
            cost_model_digest="digest",
            data_digest="digest",
            parameter_digest="digest",
            attribution=Attribution(funding=Decimal("2000"), fees=Decimal("20")),
            n_events=100,
            n_trades=10,
            extra={
                "maker_fill_rate": 0.88,
                "mean_unhedged_duration_min": 3.2,
                "net_sharpe": 2.10,
                "annualized_net_return_pct": 12.5,
                "max_drawdown_pct": 2.8,
            },
        )
        taker_art = CryptoEvidenceArtifact(
            hypothesis_id="CRYPTO-004",
            fill_model="taker_vs_mid_plus_spread",
            can_qualify=True,
            partition="OOS_TAKER",
            cost_model_digest="digest",
            data_digest="digest",
            parameter_digest="digest",
            attribution=Attribution(),
            n_events=100,
            n_trades=10,
            extra={"net_sharpe": 1.10},  # delta = 2.10 - 1.10 = 1.00 >= 0.80
        )

        result = evaluate_crypto_004_gates(oos_art, taker_art, prereg)
        assert result["verdict"] == "candidate"
        assert all(result["gates"].values())
        assert result["metrics"]["sharpe_delta"] == pytest.approx(1.00)

    def test_failed_gate_evaluates_to_negative_result_with_rule_8_failure_mode(self):
        prereg = load_preregistration_004(PREREG_PATH)
        oos_art = CryptoEvidenceArtifact(
            hypothesis_id="CRYPTO-004",
            fill_model="maker_post_only_with_15m_taker_fallback",
            can_qualify=True,
            partition="OOS",
            cost_model_digest="digest",
            data_digest="digest",
            parameter_digest="digest",
            attribution=Attribution(funding=Decimal("150"), fees=Decimal("50")),
            n_events=100,
            n_trades=10,
            extra={
                "maker_fill_rate": 0.85,
                "mean_unhedged_duration_min": 3.8,
                "net_sharpe": 0.95,  # Fails Gate 4 (< 1.50)
                "annualized_net_return_pct": 3.2,  # Fails Gate 4 (< 8.0%)
                "max_drawdown_pct": 1.5,
            },
        )
        taker_art = CryptoEvidenceArtifact(
            hypothesis_id="CRYPTO-004",
            fill_model="taker_vs_mid_plus_spread",
            can_qualify=True,
            partition="OOS_TAKER",
            cost_model_digest="digest",
            data_digest="digest",
            parameter_digest="digest",
            attribution=Attribution(),
            n_events=100,
            n_trades=10,
            extra={"net_sharpe": 0.40},
        )

        result = evaluate_crypto_004_gates(oos_art, taker_art, prereg)
        assert result["verdict"] == "negative_result"
        assert result["gates"]["gate_4_net_economic_carry_hurdle"] is False
        assert result["failure_mode"] == "execution_constrained"
        assert result["failure_mode_confidence"] == "high"


class TestEndToEndCrypto004Screen:
    def test_run_crypto_004_generates_bundle(self, tmp_path):
        manifest = _manifest()
        prereg = load_preregistration_004(PREREG_PATH)
        t0_is = datetime.fromisoformat("2024-08-01T00:00:00+00:00")
        t0_oos = datetime.fromisoformat("2025-08-01T00:00:00+00:00")

        events = []
        for i in range(12):
            ts = t0_is + timedelta(days=25 * i)
            events.append(_make_funding_event(manifest, f"is_{i}", ts.isoformat(), "0.0003"))

        for i in range(12):
            ts = t0_oos + timedelta(days=25 * i)
            events.append(_make_funding_event(manifest, f"oos_{i}", ts.isoformat(), "0.00015"))

        events.sort(key=lambda e: e.occurred_at)
        tmp_out = tmp_path / "test_bundle.json"
        bundle = run_crypto_004(events, manifest, prereg, output_path=tmp_out)

        assert bundle["hypothesis_id"] == "CRYPTO-004"
        assert "is" in bundle
        assert "oos" in bundle
        assert "taker_oos" in bundle
        assert "gates" in bundle
        assert tmp_out.exists()


class TestExecutionImportBan:
    def test_crypto_screen_004_cannot_import_execution(self):
        banned_imports = (
            "from titan.execution",
            "import titan.execution",
            "from titan.runtime",
            "from titan.portfolio",
        )
        text = SCREEN_004_PY.read_text(encoding="utf-8")
        for token in banned_imports:
            assert token not in text, f"{token} found in {SCREEN_004_PY}"
        assert "import TradeIntent" not in text
        assert "import PaperSession" not in text
        assert "import BrokerAdapter" not in text
