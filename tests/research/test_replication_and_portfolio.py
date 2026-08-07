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

def test_replication_engine_computes_real_correlation():
    engine = ReplicationEngine()
    sc = OptimizationValidationScorecard(
        strategy_id="orb", timeframe="15m", universe=("SPY", "QQQ"),
        best_params={"oos_sharpe": 1.2}, avg_plateau_stability=0.8,
        avg_plateau_coverage=0.25, cross_instrument_consistency=0.8,
        walk_forward_passed=True, bootstrap_passed=True,
        passed_all_checks=True, rejection_reasons=(),
    )
    primary = [0.001, 0.002, -0.001, 0.003, -0.002, 0.0015]
    # Perfectly positively correlated replication series
    same = [2.0 * x for x in primary]
    rep_pos = engine.evaluate_replication(
        "H-CORR", sc, sc, primary_returns=primary, replication_returns=same)
    assert abs(rep_pos.correlation_between_returns - 1.0) < 1e-3
    assert rep_pos.confidence_level == "HIGH"  # real OOS Sharpes in [1.0, 1.5)

    neg = [-x for x in primary]
    rep_neg = engine.evaluate_replication(
        "H-CORR-N", sc, sc, primary_returns=primary, replication_returns=neg)
    assert abs(rep_neg.correlation_between_returns + 1.0) < 1e-3


def test_portfolio_impact_computes_real_drawdown_contribution():
    evaluator = PortfolioImpactEvaluator()
    # Baseline portfolio: smooth positive returns => ~zero drawdown
    existing = [[0.005] * 8]
    # Candidate crashes hard mid-series
    crash = [0.005, 0.005, -0.50, 0.005, 0.005, 0.005, 0.005, 0.005]
    report = evaluator.evaluate_candidate("CRASH", crash, existing)
    # Real series math: equal-weighted combined series drops ~24.5% at the crash
    assert report.marginal_drawdown_contribution_pct > 20.0
    assert report.marginal_drawdown_contribution_pct < 30.0

    # A benign candidate (no crash) contributes far less drawdown
    benign = [0.005, -0.002, 0.003, 0.004, -0.001, 0.002, 0.003, -0.001]
    report2 = evaluator.evaluate_candidate("BENIGN", benign, existing)
    assert report2.marginal_drawdown_contribution_pct < report.marginal_drawdown_contribution_pct


def test_portfolio_impact_fails_closed_without_return_series():
    evaluator = PortfolioImpactEvaluator()
    report = evaluator.evaluate_candidate("EMPTY", [])          # no candidate series
    assert report.adds_portfolio_value is False
    report2 = evaluator.evaluate_candidate("SHORT", [0.01, 0.01])  # < 5 obs
    assert report2.adds_portfolio_value is False
    assert report2.max_correlation_with_existing == 1.0


def test_replication_fails_closed_on_self_referential_series():
    """F1 regression: passing the SAME series object as primary_returns and
    replication_returns must fail closed (correlation ~1.0 is not independent
    replication)."""
    engine = ReplicationEngine()
    sc = OptimizationValidationScorecard(
        strategy_id="orb", timeframe="15m", universe=("SPY", "QQQ"),
        best_params={"oos_sharpe": 1.8}, avg_plateau_stability=0.85,
        avg_plateau_coverage=0.3, cross_instrument_consistency=0.8,
        walk_forward_passed=True, bootstrap_passed=True,
        passed_all_checks=True, rejection_reasons=(),
    )
    series = [0.001, 0.002, -0.001, 0.003, -0.002, 0.0015]
    report = engine.evaluate_replication(
        "H-SELF", sc, sc, primary_returns=series, replication_returns=series)
    assert report.replication_passed is False
    assert report.confidence_level == "LOW"


def _selfref_scorecard():
    return OptimizationValidationScorecard(
        strategy_id="orb", timeframe="15m", universe=("SPY", "QQQ"),
        best_params={"oos_sharpe": 1.8}, avg_plateau_stability=0.85,
        avg_plateau_coverage=0.3, cross_instrument_consistency=0.8,
        walk_forward_passed=True, bootstrap_passed=True,
        passed_all_checks=True, rejection_reasons=(),
    )


def test_replication_fails_closed_on_copied_content_series():
    """F1-provenance regression (CodeRabbit #15): a copied series — content-equal
    to primary but a DISTINCT object — must fail closed as non-independent
    replication. Identity alone is insufficient; shared provenance is the real
    violation."""
    engine = ReplicationEngine()
    sc = _selfref_scorecard()
    primary = [0.001, 0.002, -0.001, 0.003, -0.002, 0.0015]
    copied = list(primary)  # distinct object, identical content
    report = engine.evaluate_replication(
        "H-COPY", sc, sc, primary_returns=primary, replication_returns=copied,
        primary_exp_id="EXP-A", replication_exp_id="EXP-B",
    )
    assert report.replication_passed is False


def test_replication_fails_closed_on_shared_experiment_provenance():
    """F1-provenance regression: identical experiment IDs on both sides mean a
    single run is being passed as its own replication — not independent."""
    engine = ReplicationEngine()
    sc = _selfref_scorecard()
    primary = [0.001, 0.002, -0.001, 0.003, -0.002, 0.0015]
    report = engine.evaluate_replication(
        "PR-SHARED", sc, sc,
        primary_returns=primary, replication_returns=[x * 2 for x in primary],
        primary_exp_id="EXP-X", replication_exp_id="EXP-X",
    )
    assert report.replication_passed is False
