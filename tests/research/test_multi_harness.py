"""Tests for multi-instrument validation harness."""

import pytest

from titan.research.gate import check_min_trades
from titan.research.hypothesis import Hypothesis
from titan.research.metrics import (
    compute_effective_trades,
    compute_pairwise_correlations,
)
from titan.research.multi_harness import (
    InstrumentSpec,
    MultiInstrumentHarness,
    MultiInstrumentReport,
)

SPY_PATH = "tests/fixtures/market/spy_2020_2024.csv"
QQQ_PATH = "tests/fixtures/market/qqq_2020_2024.csv"


def _spy_qqq_hypothesis() -> Hypothesis:
    return Hypothesis(
        id="multi-ma-crossover",
        title="MA crossover across SPY + QQQ",
        economic_rationale="Trend following works on large-cap equity ETFs.",
        strategy_id="moving-average-crossover",
        strategy_params={"fast": 5, "slow": 20},
        instrument="SPY,QQQ",
        universe="SPY + QQQ",
        calendar="2020-01-02 to 2024-12-31",
        train_period="2020-01-02 to 2022-12-31",
        test_period="2023-01-01 to 2024-12-31",
        success_criteria=["Sharpe > 0 OOS"],
        failure_criteria=[],
        costs="1.0 bps commission, 0.5 bps slippage",
        expected_trade_frequency="~26 trades/year (biweekly)",
        sample_adequacy_policy="Path A",
    )


class TestMultiInstrumentHarness:
    def test_loads_and_runs_spy_qqq(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        assert isinstance(report, MultiInstrumentReport)
        assert len(report.instruments) == 2

        for spec in report.instruments:
            assert len(spec.bars) > 0
            assert len(spec.train_bars) > 0
            assert len(spec.test_bars) > 0
            assert len(spec.equity_curve) > 0
            assert spec.result is not None
            assert spec.result.total_trades > 0

        assert len(report.pooled_equity_curve) > 0
        assert report.pooled_result is not None
        assert report.total_pooled_trades > 0
        assert report.effective_trades > 0
        assert report.gate_result is not None

    def test_pooled_equity_sums_instruments(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        spy_eq = report.instruments[0].equity_curve
        qqq_eq = report.instruments[1].equity_curve
        min_len = min(len(spy_eq), len(qqq_eq))
        expected = [spy_eq[i] + qqq_eq[i] for i in range(min_len)]
        assert len(report.pooled_equity_curve) == min_len
        assert report.pooled_equity_curve == expected

    def test_effective_trades_no_discount_low_corr(self):
        result = compute_effective_trades(100, 2, 0.1)
        assert result == 100.0

    def test_effective_trades_discount_high_corr(self):
        result = compute_effective_trades(100, 2, 0.8)
        expected = 100 / (1 + 0.8)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_effective_trades_at_corr_threshold(self):
        result = compute_effective_trades(100, 3, 0.3)
        expected = 100 / (1 + 0.3 * 2)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_effective_trades_below_30_gate_rejects(self):
        effective = compute_effective_trades(10, 2, 0.9)
        assert effective < 30
        gate = check_min_trades(int(round(effective)))
        assert gate.passed is False

    def test_effective_trades_above_30_gate_passes(self):
        effective = compute_effective_trades(100, 2, 0.3)
        assert effective >= 30
        gate = check_min_trades(int(round(effective)))
        assert gate.passed is True

    def test_gate_uses_effective_trades(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        assert report.gate_result.trade_count == int(round(report.effective_trades))

    def test_pairwise_correlation_computed(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        assert len(report.correlations) == 1
        corr = report.correlations[0]
        assert corr.instrument_a == "SPY"
        assert corr.instrument_b == "QQQ"
        assert -1.0 <= corr.pearson_r <= 1.0
        assert corr.observation_count > 0

    def test_hypothesis_result_in_report(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        assert report.hypothesis.id == hypothesis.id
        assert report.hypothesis.title == hypothesis.title

    def test_instrument_spec_fields_populated(self):
        hypothesis = _spy_qqq_hypothesis()
        instruments = [
            InstrumentSpec(instrument_id="SPY", data_path=SPY_PATH),
            InstrumentSpec(instrument_id="QQQ", data_path=QQQ_PATH),
        ]
        harness = MultiInstrumentHarness(hypothesis, instruments)
        report = harness.run()

        for spec in report.instruments:
            assert spec.train_bars is not None
            assert spec.test_bars is not None
            assert spec.equity_curve is not None
            assert spec.trades is not None


class TestComputePairwiseCorrelations:
    def test_identical_series_returns_1(self):
        bars = [
            {"timestamp": "2024-01-01", "close": 100.0},
            {"timestamp": "2024-01-02", "close": 102.0},
            {"timestamp": "2024-01-03", "close": 101.0},
            {"timestamp": "2024-01-04", "close": 103.0},
        ]
        result = compute_pairwise_correlations([("A", bars), ("B", bars)])
        assert len(result) == 1
        assert result[0].pearson_r == pytest.approx(1.0, abs=1e-6)
        assert result[0].observation_count == 3

    def test_inverse_series_returns_neg_1(self):
        bars_a = [
            {"timestamp": "2024-01-01", "close": 100.0},
            {"timestamp": "2024-01-02", "close": 102.0},
            {"timestamp": "2024-01-03", "close": 101.0},
            {"timestamp": "2024-01-04", "close": 103.0},
        ]
        inv_close = [100.0, 98.0, 99.0, 97.0]
        bars_b = [
            {"timestamp": b["timestamp"], "close": inv_close[i]}
            for i, b in enumerate(bars_a)
        ]
        result = compute_pairwise_correlations([("A", bars_a), ("B", bars_b)])
        assert len(result) == 1
        assert result[0].pearson_r == pytest.approx(-1.0, abs=0.01)
        assert result[0].observation_count == 3

    def test_fewer_than_two_common_dates(self):
        bars_a = [{"timestamp": "2024-01-01", "close": 100.0}]
        bars_b = [{"timestamp": "2024-01-02", "close": 102.0}]
        result = compute_pairwise_correlations([("A", bars_a), ("B", bars_b)])
        assert len(result) == 0

    def test_three_instruments_three_pairs(self):
        bars = [
            {"timestamp": "2024-01-01", "close": 100.0},
            {"timestamp": "2024-01-02", "close": 102.0},
            {"timestamp": "2024-01-03", "close": 101.0},
        ]
        result = compute_pairwise_correlations([
            ("A", bars), ("B", bars), ("C", bars),
        ])
        assert len(result) == 3
        for c in result:
            assert c.pearson_r == pytest.approx(1.0, abs=1e-6)


class TestComputeEffectiveTrades:
    def test_two_instruments_low_corr_no_discount(self):
        assert compute_effective_trades(60, 2, 0.1) == 60.0

    def test_two_instruments_high_corr(self):
        result = compute_effective_trades(60, 2, 0.9)
        assert result == pytest.approx(60 / 1.9, rel=1e-6)

    def test_four_instruments(self):
        result = compute_effective_trades(120, 4, 0.5)
        expected = 120 / (1 + 0.5 * 3)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_zero_total_trades(self):
        assert compute_effective_trades(0, 2, 0.5) == 0.0

    def test_single_instrument(self):
        assert compute_effective_trades(30, 1, 0.5) == 30.0

    def test_at_correlation_threshold(self):
        result = compute_effective_trades(100, 3, 0.3)
        expected = 100 / (1 + 0.3 * 2)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_below_threshold_no_discount(self):
        assert compute_effective_trades(30, 5, 0.29) == 30.0
