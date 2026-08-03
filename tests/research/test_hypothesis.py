"""Tests for hypothesis preregistration."""

import pytest
from titan.research.hypothesis import Hypothesis


class TestHypothesis:
    def test_create_minimal(self):
        h = Hypothesis(
            id="test-001",
            title="Test hypothesis",
            economic_rationale="Testing the hypothesis system",
            strategy_id="ma-crossover",
            strategy_params={"fast": 5, "slow": 20},
            instrument="SPY",
            universe="SPY only",
            calendar="2020-01-01 to 2024-12-31",
            train_period="2020-01-01",
            test_period="2023-01-01",
            success_criteria=["Sharpe > 0.5"],
            failure_criteria=["Sharpe < 0"],
            costs="1 bps",
            expected_trade_frequency="~26 trades/year",
            sample_adequacy_policy="Path A",
        )
        assert h.id == "test-001"
        assert h.status == "preregistered"
        assert h.preregistered_at != ""

    def test_to_dict_round_trip(self):
        h = Hypothesis(
            id="test-002",
            title="Round trip test",
            economic_rationale="Test",
            strategy_id="ma-crossover",
            strategy_params={"fast": 10, "slow": 30},
            instrument="QQQ",
            universe="QQQ only",
            calendar="2021-01-01 to 2023-12-31",
            train_period="2021-01-01",
            test_period="2022-01-01",
            success_criteria=["Sharpe > 0.3", "Win rate > 40%"],
            failure_criteria=["Return < 0"],
            costs="2 bps",
            expected_trade_frequency="~52 trades/year",
            sample_adequacy_policy="Path A",
            notes="Test notes",
        )
        d = h.to_dict()
        h2 = Hypothesis.from_dict(d)
        assert h2.id == h.id
        assert h2.title == h.title
        assert h2.strategy_params == h.strategy_params
        assert h2.success_criteria == h.success_criteria
        assert h2.preregistered_at == h.preregistered_at

    def test_frozen(self):
        h = Hypothesis(
            id="test-003",
            title="Frozen test",
            economic_rationale="Test immutability",
            strategy_id="ma-crossover",
            strategy_params={"fast": 5},
            instrument="SPY",
            universe="SPY",
            calendar="2020-01-01",
            train_period="2020-01-01",
            test_period="2023-01-01",
            success_criteria=["Sharpe > 0"],
            failure_criteria=["Sharpe < 0"],
            costs="0",
            expected_trade_frequency="N/A",
            sample_adequacy_policy="Path A",
        )
        with pytest.raises(Exception):
            h.id = "changed"

    def test_path_b_requires_evidence_standard(self):
        with pytest.raises(ValueError, match="Path B hypotheses must declare"):
            Hypothesis(
                id="test-004",
                title="Path B without evidence",
                economic_rationale="Test",
                strategy_id="mean-reversion",
                strategy_params={"window": 20},
                instrument="SPY",
                universe="SPY",
                calendar="2020-01-01",
                train_period="2020-01-01",
                test_period="2023-01-01",
                success_criteria=["Sharpe > 0"],
                failure_criteria=["Sharpe < 0"],
                costs="0",
                expected_trade_frequency="~2 trades/year",
                sample_adequacy_policy="Path B",
            )

    def test_path_b_accepts_with_evidence_standard(self):
        h = Hypothesis(
            id="test-005",
            title="Path B with evidence",
            economic_rationale="Test",
            strategy_id="mean-reversion",
            strategy_params={"window": 20},
            instrument="SPY",
            universe="SPY",
            calendar="2020-01-01",
            train_period="2020-01-01",
            test_period="2023-01-01",
            success_criteria=["Sharpe > 0"],
            failure_criteria=["Sharpe < 0"],
            costs="0",
            expected_trade_frequency="~2 trades/year",
            sample_adequacy_policy="Path B",
            path_b_evidence_standard="10-year history with walk-forward validation",
        )
        assert h.sample_adequacy_policy == "Path B"
        assert h.path_b_evidence_standard == "10-year history with walk-forward validation"
