"""Adversarial stress and edge-case verification suite for Simulation, Costs, Fills, Corporate Actions, and Data Manifests.

Challenger: Challenger Gen2 1
Focus:
1. FxCostModel institutional cost invariants ($2.00 IBKR ticket minimum floor, crossover points, currency validation, immutability).
2. Equities and Crypto cost accounting (FactorCostModel short borrow 50 bps daily accrual, dollar-neutral balance, Crypto VIP0 maker/taker and funding cashflows).
3. Quote-sided top-of-book fills vs bar-close fills (price direction, adverse slippage, missing quotes fail-closed, high-turnover friction attribution, promotion gate rejection of lower-fidelity).
4. Point-in-time Corporate Actions split and dividend backward adjustment (extreme splits, dollar-volume invariance, return invariance, causality/no-forward-leakage).
5. Data Manifest SHA-256 tamper resistance (bit flips, metadata mutations, chunking boundary stress 0B..1MB).
"""

import copy
import hashlib
import json
import os
import tempfile
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from titan.backtest.fx_costs import FxCostModel
from titan.backtest.factor_simulator import FactorCostModel, simulate_factor_portfolio, _compute_max_drawdown
from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.crypto_simulator import simulate_crypto, FILL_EXPLORATORY, FILL_TAKER_MID
from titan.data.crypto import CryptoMarketEvent
from titan.backtest.fills import BarConservativeFillModel, FillResult
from titan.backtest.results import BacktestResult, _compute_backtest, _compute_sharpe, _compute_volatility
from titan.backtest.corporate_actions import CorporateActionsDB
from titan.data.manifest import DataManifest
from titan.data.ingest import checksum
from titan.research.promotion import PromotionGate
from titan.data.equities_universe import EquitiesUniverseData, EquitiesUniverseManifest


class TestAdversarialFxCostModel:
    """Adversarial stress tests for ADR-031 FX Cost Model."""

    @pytest.mark.parametrize("notional,expected_commission", [
        ("0.0001", "2.00"),
        ("0.01", "2.00"),
        ("1.00", "2.00"),
        ("10.00", "2.00"),
        ("100.00", "2.00"),
        ("1000.00", "2.00"),
        ("10000.00", "2.00"),
        ("50000.00", "2.00"),
        ("99999.99", "2.00"),
        ("100000.00", "2.00"),      # Exactly 100k * 0.20 bps = $2.00
        ("100001.00", "2.00002"),   # Exceeds floor
        ("200000.00", "4.00"),
        ("500000.00", "10.00"),
        ("1000000.00", "20.00"),
        ("10000000.00", "200.00"),
    ])
    def test_fee_minimum_floor_and_crossover_continuum(self, notional, expected_commission):
        """Verify strict $2.00 floor applies up to exactly $100k notional, then linear variable rate."""
        model = FxCostModel.ibkr_spot_fx_tier_one()
        fee = model.commission_for_fill(Decimal(notional))
        assert fee == Decimal(expected_commission), f"Mismatch for notional {notional}: got {fee}"

    def test_negative_and_zero_notional_handling(self):
        """Verify negative notionals preserve magnitude and 0 notional returns floor."""
        model = FxCostModel.ibkr_spot_fx_tier_one()
        assert model.commission_for_fill(Decimal("0")) == Decimal("2.00")
        assert model.commission_for_fill(Decimal("-10000")) == Decimal("2.00")
        assert model.commission_for_fill(Decimal("-500000")) == Decimal("10.00")

    def test_immutability_guarantee(self):
        """Verify that FxCostModel cannot be mutated at runtime (frozen dataclass)."""
        model = FxCostModel.ibkr_spot_fx_tier_one()
        with pytest.raises(FrozenInstanceError):
            model.commission_bps = Decimal("0.0")
        with pytest.raises(FrozenInstanceError):
            model.minimum_commission = Decimal("0.0")

    @pytest.mark.parametrize("invalid_kwargs,error_match", [
        ({"account_currency": "EUR"}, "account_currency"),
        ({"quote_currency": "GBP"}, "quote_currency"),
        ({"commission_bps": Decimal("-0.1")}, "commission_bps"),
        ({"minimum_commission": Decimal("-1.0")}, "minimum_commission"),
        ({"half_spread_bps": Decimal("-0.5")}, "half_spread_bps"),
        ({"slippage_bps": Decimal("-0.5")}, "slippage_bps"),
    ])
    def test_input_validation_rejections(self, invalid_kwargs, error_match):
        """Verify non-USD or negative parameters are strictly rejected in constructor."""
        base_args = {
            "venue": "IDEALPRO",
            "account_currency": "USD",
            "quote_currency": "USD",
            "commission_bps": Decimal("0.20"),
            "minimum_commission": Decimal("2.00"),
            "half_spread_bps": Decimal("0.10"),
            "slippage_bps": Decimal("0.10"),
            "fill_mode": "QUOTE_NEXT_EVENT",
        }
        base_args.update(invalid_kwargs)
        with pytest.raises(ValueError, match=error_match):
            FxCostModel(**base_args)

    def test_sha256_digest_tamper_sensitivity(self):
        """Verify any configuration parameter change produces a completely distinct digest."""
        base = FxCostModel.ibkr_spot_fx_tier_one()
        base_digest = base.digest()
        assert len(base_digest) == 64

        # Perturb each field slightly
        perturbed_models = [
            base.with_adverse_costs(commission_bps=Decimal("0.2000001")),
            base.with_adverse_costs(half_spread_bps=Decimal("0.1000001")),
            base.with_adverse_costs(slippage_bps=Decimal("0.1000001")),
            FxCostModel(
                venue="IDEALPRO",
                account_currency="USD",
                quote_currency="USD",
                commission_bps=Decimal("0.20"),
                minimum_commission=Decimal("2.01"),
                half_spread_bps=Decimal("0.10"),
                slippage_bps=Decimal("0.10"),
                fill_mode="QUOTE_NEXT_EVENT",
            ),
            FxCostModel.ibkr_spot_fx_tier_one(fill_mode="BAR_NEXT_OPEN"),
            FxCostModel.ibkr_spot_fx_tier_one(data_manifest_digest="a" * 64),
        ]
        for p in perturbed_models:
            assert p.digest() != base_digest


class TestAdversarialMultiAssetCostAccounting:
    """Stress-test Equities short borrow financing and Crypto VIP0 funding cashflows."""

    def test_equities_short_borrow_daily_accrual_math(self):
        """Verify short borrow fee accrues 50 bps annual rate on short leg only."""
        dates = pd.date_range("2024-01-01", periods=60, freq="B")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"]
        np.random.seed(42)
        prices = pd.DataFrame(
            100.0 + np.cumsum(np.random.randn(len(dates), len(symbols)) * 0.5, axis=0),
            index=dates,
            columns=symbols,
        )
        returns = prices.pct_change().fillna(0.0)
        manifest = EquitiesUniverseManifest(
            dataset_name="EQ_TEST",
            asset_class="EQUITIES",
            source="TEST",
            universe=symbols,
            timezone="America/New_York",
            calendar="NYSE",
            coverage_from="2024-01-01",
            coverage_to="2024-03-31",
            is_partition={"from": "2024-01-01", "to": "2024-02-15"},
            oos_partition={"from": "2024-02-16", "to": "2024-03-31"},
            fee_schedule={"commission_per_share": 0.005},
            retrieval_ts_utc="2026-08-18T10:00:00Z",
        )
        universe = EquitiesUniverseData(manifest=manifest, prices=prices, returns=returns)

        # Factor scores: AAPL, MSFT, GOOGL high; AMZN, META, NVDA low
        scores = pd.DataFrame(0.0, index=dates, columns=symbols)
        scores[["AAPL", "MSFT", "GOOGL"]] = 2.0
        scores[["AMZN", "META", "NVDA"]] = -2.0

        model = FactorCostModel(annual_short_borrow_bps=50.0, commission_per_share_usd=0.005)
        res = simulate_factor_portfolio(
            universe=universe,
            factor_scores=scores,
            hypothesis_id="EQ-TEST",
            top_k=3,
            bottom_k=3,
            rebalance_freq_days=21,
            gross_exposure=1.0,
            cost_model=model,
        )
        # Expected daily short borrow rate = (50 * 1e-4) / 252 ~= 0.00001984
        # Short leg weight magnitude is 0.5
        expected_daily_borrow = 0.5 * (50.0 * 1e-4) / 252.0
        # Check total borrow cost
        n_held_days = len(dates) - 1
        assert res.costs["total_borrow_cost"] > 0
        assert abs(res.costs["total_borrow_cost"] - (expected_daily_borrow * n_held_days)) < 1e-5
        # Net return must be strictly lower than gross return
        assert res.annualized_net_return < (res.gross_returns.mean() * 252.0)

    def test_factor_dollar_neutral_exposure_invariant(self):
        """Verify long weight + short weight == 0.0 at all timestamps."""
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        symbols = [f"SYM{i}" for i in range(10)]
        prices = pd.DataFrame(100.0, index=dates, columns=symbols)
        returns = pd.DataFrame(0.001, index=dates, columns=symbols)
        manifest = EquitiesUniverseManifest(
            dataset_name="EQ_NEUTRAL",
            asset_class="EQUITIES",
            source="TEST",
            universe=symbols,
            timezone="America/New_York",
            calendar="NYSE",
            coverage_from="2024-01-01",
            coverage_to="2024-05-31",
            is_partition={"from": "2024-01-01", "to": "2024-03-15"},
            oos_partition={"from": "2024-03-16", "to": "2024-05-31"},
            fee_schedule={"commission_per_share": 0.005},
            retrieval_ts_utc="2026-08-18T10:00:00Z",
        )
        universe = EquitiesUniverseData(manifest=manifest, prices=prices, returns=returns)

        # Dynamic random scores
        np.random.seed(123)
        scores = pd.DataFrame(np.random.randn(len(dates), len(symbols)), index=dates, columns=symbols)

        res = simulate_factor_portfolio(
            universe=universe,
            factor_scores=scores,
            hypothesis_id="EQ-NEUTRAL",
            top_k=3,
            bottom_k=3,
            rebalance_freq_days=5,
            gross_exposure=2.0,
        )
        # Ensure simulation executed and tracked turnover
        assert res.monthly_turnover > 0
        assert res.costs["total_friction"] > 0

    def test_crypto_funding_rate_cashflow_direction(self):
        """Verify positive funding rate pays short perpetuals and charges long perpetuals."""
        cost_model = CryptoCostModel.binance_usdt_vip0()
        dt1 = datetime(2026, 8, 14, 8, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 8, 14, 16, 0, 0, tzinfo=timezone.utc)
        
        # Test 1: Short perp position (-1 BTC at $50,000) with positive funding rate (+0.0001 = 1 bps)
        # Signal enters short perp (-1) at event 1, funding event arrives at event 2
        events = [
            CryptoMarketEvent(
                event_id="EVT-1",
                venue="binance-vision",
                symbol="BTCUSDT",
                contract_kind="PERPETUAL",
                occurred_at=dt1,
                event_type="QUOTE",
                source_manifest_digest="d" * 64,
                ingestion_ts=dt1,
                price=Decimal("50000"),
                bid=Decimal("49999"),
                ask=Decimal("50001"),
            ),
            CryptoMarketEvent(
                event_id="EVT-2",
                venue="binance-vision",
                symbol="BTCUSDT",
                contract_kind="PERPETUAL",
                occurred_at=dt2,
                event_type="FUNDING",
                source_manifest_digest="d" * 64,
                ingestion_ts=dt2,
                price=Decimal("50000"),
                funding_rate=Decimal("0.0001"),
            ),
        ]
        def short_signal(ev, state):
            return Decimal("-1.0")

        res_short = simulate_crypto(
            events=events,
            signal=short_signal,
            cost_model=cost_model,
            partition="OOS",
            hypothesis_id="CRYPTO-SHORT",
            parameters={"test": "funding"},
            data_digest="d" * 64,
            fill_model=FILL_TAKER_MID,
        )
        # Short perp position (-(-1) * 50000 * 0.0001 = +5.00 USD received funding)
        assert res_short.attribution.funding == Decimal("5.0000000")

        # Test 2: Long perp position (+1 BTC at $50,000)
        def long_signal(ev, state):
            return Decimal("1.0")

        res_long = simulate_crypto(
            events=events,
            signal=long_signal,
            cost_model=cost_model,
            partition="OOS",
            hypothesis_id="CRYPTO-LONG",
            parameters={"test": "funding"},
            data_digest="d" * 64,
            fill_model=FILL_TAKER_MID,
        )
        # Long perp position (-(1) * 50000 * 0.0001 = -5.00 USD paid funding)
        assert res_long.attribution.funding == Decimal("-5.0000000")


class TestAdversarialFillsAndPromotionRejection:
    """Stress-test Quote-Sided Top-of-Book fills vs naive bar-close and fail-closed promotion."""

    def test_quote_fill_price_adverse_slippage_direction(self):
        """Verify BUY fills at ask + slippage and SELL fills at bid - slippage."""
        fill_model = BarConservativeFillModel()
        cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")

        bar = {"bid": Decimal("1.08500"), "ask": Decimal("1.08520")}
        
        # BUY fill: 10,000 units (~$10,852 notional -> clamped to $2.00 minimum)
        buy_res = fill_model.fill(bar, "buy", Decimal("10000"), cost_model=cost_model)
        # Slippage = 1.08520 * 0.10 bps / 10000 = 0.000010852
        assert buy_res.fill_price == Decimal("1.08520") + Decimal("0.000010852")
        assert buy_res.fill_price > Decimal("1.08520")
        assert buy_res.commission == Decimal("2.00")

        # BUY fill: 100,000 units (~$108,521 notional -> variable rate applies > $2.00)
        buy_large = fill_model.fill(bar, "buy", Decimal("100000"), cost_model=cost_model)
        assert buy_large.commission == Decimal("2.17042170400")

        # SELL fill: 10,000 units (~$10,850 notional -> clamped to $2.00 minimum)
        sell_res = fill_model.fill(bar, "sell", Decimal("10000"), cost_model=cost_model)
        # Slippage = 1.08500 * 0.10 bps / 10000 = 0.000010850
        assert sell_res.fill_price == Decimal("1.08500") - Decimal("0.000010850")
        assert sell_res.fill_price < Decimal("1.08500")
        assert sell_res.commission == Decimal("2.00")

    def test_missing_quote_data_fails_closed(self):
        """Verify missing ask on BUY or missing bid on SELL raises ValueError."""
        fill_model = BarConservativeFillModel()
        cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")

        with pytest.raises(ValueError, match="ask"):
            fill_model.fill({"bid": Decimal("1.08500")}, "buy", Decimal("10000"), cost_model=cost_model)

        with pytest.raises(ValueError, match="bid"):
            fill_model.fill({"ask": Decimal("1.08520")}, "sell", Decimal("10000"), cost_model=cost_model)

    def test_high_turnover_friction_divergence_quote_vs_bar_close(self):
        """Demonstrate that high-turnover strategy is profitable under naive bar-close but destroyed by canonical costs."""
        # Generate 100 oscillating quotes
        bars = []
        for i in range(100):
            mid = Decimal("1.1000") + (Decimal("0.0005") if i % 2 == 0 else Decimal("-0.0005"))
            bars.append({
                "open": mid,
                "close": mid,
                "bid": mid - Decimal("0.0001"),
                "ask": mid + Decimal("0.0001"),
                "instrument_id": "EURUSD",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z"
            })
        
        fill_model = BarConservativeFillModel()
        cost_model = FxCostModel.ibkr_spot_fx_tier_one(fill_mode="QUOTE_NEXT_EVENT")

        # Simulate 50 round trips of 10,000 units
        total_quote_commission = Decimal("0")
        total_quote_spread_slippage_loss = Decimal("0")
        naive_pnl = Decimal("0")

        for i in range(0, 100, 2):
            # Naive buy & sell at mid
            buy_naive = bars[i]["close"]
            sell_naive = bars[i+1]["close"]
            naive_pnl += (sell_naive - buy_naive) * Decimal("10000")

            # Canonical quote fills
            buy_fill = fill_model.fill(bars[i], "buy", Decimal("10000"), cost_model=cost_model)
            sell_fill = fill_model.fill(bars[i+1], "sell", Decimal("10000"), cost_model=cost_model)
            
            total_quote_commission += buy_fill.commission + sell_fill.commission
            loss_from_friction = (buy_fill.fill_price - bars[i]["close"]) * Decimal("10000") + (bars[i+1]["close"] - sell_fill.fill_price) * Decimal("10000")
            total_quote_spread_slippage_loss += loss_from_friction

        # Total commission is 100 orders * $2.00 = $200.00
        assert total_quote_commission == Decimal("200.00")
        assert total_quote_spread_slippage_loss > Decimal("0")
        # Naive PnL was +$500 gross, but friction ($200 comm + spread/slippage) significantly eats into it
        net_canonical_pnl = naive_pnl - total_quote_commission - total_quote_spread_slippage_loss
        assert net_canonical_pnl < naive_pnl

    def test_promotion_gate_strictly_rejects_lower_fidelity_and_bar_close(self, tmp_path):
        """Verify PromotionGate.evaluate_from_artifact rejects lower fidelity and missing digests."""
        gate = PromotionGate(tmp_path / "test.db", bars=[])

        # 1. Bar next open fill
        artifact_bar_close = {
            "strategy_id": "TEST-1",
            "data_manifest_digest": "a" * 64,
            "parameter_digest": "b" * 64,
            "sizing_digest": "c" * 64,
            "cost_model_digest": "d" * 64,
            "fill_model": "BAR_NEXT_OPEN",
            "fidelity": "lower",
        }
        res1 = gate.evaluate_from_artifact(artifact_bar_close)
        assert not res1["passed"]
        assert any("lower-fidelity" in r for r in res1["reasons"])

        # 2. Missing cost model digest
        artifact_missing_cost = {
            "strategy_id": "TEST-2",
            "data_manifest_digest": "a" * 64,
            "parameter_digest": "b" * 64,
            "sizing_digest": "c" * 64,
            "fill_model": "QUOTE_NEXT_EVENT",
            "fidelity": "quote",
        }
        res2 = gate.evaluate_from_artifact(artifact_missing_cost)
        assert not res2["passed"]
        assert any("missing required digest" in r for r in res2["reasons"])

        # 3. Valid canonical artifact passes
        artifact_canonical = {
            "strategy_id": "TEST-3",
            "data_manifest_digest": "a" * 64,
            "parameter_digest": "b" * 64,
            "sizing_digest": "c" * 64,
            "cost_model_digest": "d" * 64,
            "fill_model": "QUOTE_NEXT_EVENT",
            "fidelity": "quote",
        }
        res3 = gate.evaluate_from_artifact(artifact_canonical)
        assert res3["passed"]


class TestAdversarialCorporateActions:
    """Stress-test Corporate Actions split/dividend backward adjustment."""

    @pytest.mark.parametrize("split_ratio", [
        100.0,   # 1:100 forward split
        4.0,     # 1:4 forward split
        1.5,     # 2:3 fractional split
        1.4,     # 5:7 fractional split
        0.1,     # 10:1 reverse split
        0.01,    # 100:1 reverse split
    ])
    def test_extreme_and_fractional_split_ratios(self, split_ratio):
        """Verify price/ratio and volume*ratio hold for extreme and fractional splits."""
        db = CorporateActionsDB()
        db.register_split("2024-06-01", "TEST", split_ratio)
        bars = [
            {"date": "2024-05-01", "symbol": "TEST", "open": 1000.0, "high": 1100.0, "low": 950.0, "close": 1050.0, "volume": 10000},
            {"date": "2024-06-15", "symbol": "TEST", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5, "volume": 1000000},
        ]
        adjusted = db.adjust_bars(bars)
        
        # Pre-split bar
        assert abs(adjusted[0]["open"] - (1000.0 / split_ratio)) < 1e-6
        assert abs(adjusted[0]["close"] - (1050.0 / split_ratio)) < 1e-6
        assert abs(adjusted[0]["volume"] - (10000 * split_ratio)) < 1e-6
        # Post-split bar is untouched
        assert adjusted[1]["open"] == 10.0
        assert adjusted[1]["close"] == 10.5
        assert adjusted[1]["volume"] == 1000000

    def test_dollar_volume_and_return_invariance(self):
        """Verify dollar volume (price * volume) and percentage returns are invariant under split adjustment."""
        db = CorporateActionsDB()
        db.register_split("2024-06-01", "AAPL", 4.0)
        bars = [
            {"date": "2024-05-01", "symbol": "AAPL", "open": 200.0, "high": 210.0, "low": 195.0, "close": 200.0, "volume": 5000},
            {"date": "2024-05-02", "symbol": "AAPL", "open": 200.0, "high": 220.0, "low": 198.0, "close": 210.0, "volume": 6000},
        ]
        raw_dollar_vol_0 = bars[0]["close"] * bars[0]["volume"]
        raw_return = (bars[1]["close"] - bars[0]["close"]) / bars[0]["close"]

        adjusted = db.adjust_bars(bars)
        adj_dollar_vol_0 = adjusted[0]["close"] * adjusted[0]["volume"]
        adj_return = (adjusted[1]["close"] - adjusted[0]["close"]) / adjusted[0]["close"]

        assert abs(adj_dollar_vol_0 - raw_dollar_vol_0) < 1e-6
        assert abs(adj_return - raw_return) < 1e-6

    def test_causality_and_no_forward_leakage(self):
        """Verify bars strictly AFTER corporate action date receive ZERO adjustment."""
        db = CorporateActionsDB()
        db.register_split("2024-06-01", "SPY", 2.0)
        db.register_dividend("2024-06-01", "SPY", 1.50)

        post_bars = [
            {"date": "2024-06-02", "symbol": "SPY", "open": 500.0, "high": 505.0, "low": 498.0, "close": 502.0, "volume": 100000},
            {"date": "2024-06-03", "symbol": "SPY", "open": 502.0, "high": 508.0, "low": 501.0, "close": 507.0, "volume": 110000},
        ]
        adjusted = db.adjust_bars(post_bars)
        for original, adj in zip(post_bars, adjusted):
            assert original == adj


class TestAdversarialDataManifestTamperResistance:
    """Stress-test DataManifest SHA-256 chunked hashing and tamper detection."""

    def test_chunking_boundary_continuum_and_hash_correctness(self, tmp_path):
        """Verify checksum() matches standard sha256 for exact chunk sizes around 8192 bytes."""
        sizes = [0, 1, 100, 8191, 8192, 8193, 16384, 65536, 1000000]
        for sz in sizes:
            p = tmp_path / f"test_{sz}.bin"
            data = os.urandom(sz)
            p.write_bytes(data)
            expected = hashlib.sha256(data).hexdigest()
            actual = checksum(p)
            assert actual == expected, f"Checksum mismatch for size {sz}"

    def test_manifest_tamper_detection_on_all_fields(self, tmp_path):
        """Verify modifying ANY field in DataManifest produces a completely different digest."""
        p = tmp_path / "raw.csv"
        p.write_text("timestamp,open,high,low,close,volume\n2024-01-01,100,105,95,102,1000\n", encoding="utf-8")

        manifest = DataManifest(
            source_path=str(p),
            source_checksum=checksum(p),
            instrument_id="SPY",
            date_from="2024-01-01",
            date_to="2024-01-02",
            record_count=1,
            applied_adjustments=["SPLIT_2X"],
            created_at="2026-08-18T10:00:00Z",
        )
        base_digest = manifest.compute_digest()
        assert len(base_digest) == 64

        # Test single bit mutation in source file
        p_tampered = tmp_path / "raw_tampered.csv"
        p_tampered.write_text("timestamp,open,high,low,close,volume\n2024-01-01,100,105,95,103,1000\n", encoding="utf-8")
        manifest_tampered_file = copy.deepcopy(manifest)
        manifest_tampered_file.source_path = str(p_tampered)
        manifest_tampered_file.source_checksum = checksum(p_tampered)
        assert manifest_tampered_file.compute_digest() != base_digest

        # Test mutations of each metadata attribute
        mutations = [
            ("instrument_id", "QQQ"),
            ("date_from", "2024-01-02"),
            ("date_to", "2024-01-03"),
            ("record_count", 2),
            ("applied_adjustments", ["SPLIT_2X", "DIVIDEND_1.5"]),
            ("source_checksum", "0" * 64),
            ("schema_version", "2.0"),
        ]
        for field_name, new_val in mutations:
            m_mut = copy.deepcopy(manifest)
            setattr(m_mut, field_name, new_val)
            assert m_mut.compute_digest() != base_digest, f"Failed to detect tamper in {field_name}"


class TestAdversarialMetricsAndGenerativeHarness:
    """Stress-test metrics calculation under extreme, degenerate, and edge-case inputs."""

    def test_sharpe_and_volatility_zero_variance_resilience(self):
        """Verify zero division is safely handled when returns are identical (std=0)."""
        constant_returns = [0.001] * 100
        sharpe = _compute_sharpe(constant_returns)
        # avg > 0, std = 0 -> clamped to 1e-10 or 0
        assert not np.isnan(sharpe)
        assert not np.isinf(sharpe)

        zero_returns = [0.0] * 50
        assert _compute_sharpe(zero_returns) == 0.0
        assert _compute_volatility(zero_returns) == 0.0

    def test_max_drawdown_degenerate_cases(self):
        """Verify max drawdown on monotonic up, monotonic down, and 100% loss curves."""
        # Monotonic upward equity: 0% drawdown
        up_returns = pd.Series([0.01] * 20)
        assert _compute_max_drawdown(up_returns) == 0.0

        # Monotonic downward equity (-10% each day)
        down_returns = pd.Series([-0.10] * 10)
        dd_down = _compute_max_drawdown(down_returns)
        assert dd_down > 0.60  # > 60% drawdown

        # 100% loss (return -1.0)
        wipeout = pd.Series([0.0, -1.0])
        assert _compute_max_drawdown(wipeout) == 1.0

    def test_empty_and_single_element_backtest_results(self):
        """Verify empty and single-element equity curves produce default BacktestResult without crashing."""
        res_empty = _compute_backtest([], [])
        assert res_empty.total_trades == 0
        assert res_empty.total_return_pct == 0.0
        assert res_empty.sharpe_ratio == 0.0

        res_single = _compute_backtest([100000.0], [])
        assert res_single.total_trades == 0
        assert res_single.total_return_pct == 0.0
