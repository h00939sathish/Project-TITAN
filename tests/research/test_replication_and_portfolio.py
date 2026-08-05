"""Unit tests for Independent Replication Framework and Portfolio Impact Evaluator."""

import pytest
from titan.research.replication import ReplicationEngine
from titan.research.portfolio_impact import PortfolioImpactEvaluator
from titan.research.validators.parameter_stability import OptimizationValidationScorecard


def test_replication_engine_pass():
    engine = ReplicationEngine()
    sc_primary = OptimizationValidationScorecard(
        strategy_id="orb",
        timeframe="15m",
        universe=("SPY", "QQQ"),
        best_params={"oos_sharpe": 1.8},
        avg_plateau_stability=0.85,
        avg_plateau_coverage=0.30,
        cross_instrument_consistency=0.80,
        walk_forward_passed=True,
        bootstrap_passed=True,
        passed_all_checks=True,
        rejection_reasons=(),
    )
    sc_repl = OptimizationValidationScorecard(
        strategy_id="orb",
        timeframe="15m",
        universe=("IWM", "DIA"),
        best_params={"oos_sharpe": 1.6},
        avg_plateau_stability=0.80,
        avg_plateau_coverage=0.25,
        cross_instrument_consistency=0.80,
        walk_forward_passed=True,
        bootstrap_passed=True,
        passed_all_checks=True,
        rejection_reasons=(),
    )

    report = engine.evaluate_replication("H-001", sc_primary, sc_repl)
    assert report.replication_passed
    assert report.confidence_level == "INSTITUTIONAL"
    assert "[PASSED]" in report.summary()


def test_portfolio_impact_evaluator_adds_value():
    evaluator = PortfolioImpactEvaluator()
    candidate_returns = [0.01, -0.005, 0.02, 0.01, -0.002, 0.015]
    existing_returns = [[-0.005, 0.01, -0.01, 0.005, 0.01, -0.005]]  # Low correlation

    report = evaluator.evaluate_candidate("ORB-15M", candidate_returns, existing_returns)
    assert report.adds_portfolio_value
    assert report.incremental_sharpe > 0
    assert "[ADDS PORTFOLIO VALUE]" in report.summary()
