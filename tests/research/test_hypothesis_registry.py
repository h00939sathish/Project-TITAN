"""Unit tests for Hypothesis taxonomy, priority score, and RVA scorecard."""

import pytest
from titan.research.hypothesis import Hypothesis, HypothesisRegistry
from titan.research.yield_tracker import ResearchHealthScorecard


def test_hypothesis_priority_score_and_taxonomy():
    h = Hypothesis(
        id="H-001",
        title="Opening Auction Order Flow Imbalance",
        category="Market Microstructure",
        mechanism="Opening Auction Imbalance",
        economic_driver="Institutional Order Flow Pressure",
        economic_rationale="We believe opening imbalance reflects institutional market-on-open orders causing intraday drift.",
        kill_criteria=("Cross-instrument consistency < 50%", "Bootstrap CI crosses zero"),
        plausibility=5,
        impact=4,
        novelty=4,
        effort=2,
    )

    assert h.priority_score == 6.5  # (5 + 4 + 4) / 2
    assert "Cross-instrument consistency < 50%" in h.kill_criteria


def test_hypothesis_registry_storage(tmp_path):
    reg_path = tmp_path / "hypotheses.json"
    registry = HypothesisRegistry(reg_path)

    h = Hypothesis(
        id="H-001",
        title="Opening Auction Order Flow Imbalance",
        category="Market Microstructure",
        mechanism="Opening Auction Imbalance",
        economic_driver="Institutional Order Flow Pressure",
        economic_rationale="We believe opening imbalance reflects institutional market-on-open orders.",
        kill_criteria=("Cross-instrument consistency < 50%",),
    )

    registry.register(h)
    assert reg_path.exists()
    assert "H-001" in reg_path.read_text(encoding="utf-8")


def test_research_health_scorecard_rva():
    scorecard = ResearchHealthScorecard(
        experiments_run=12,
        rejected=10,
        refined=2,
        promoted=0,
        sample_sizes=[1000, 2000, 3000],
        oos_sharpes=[0.5, 1.1, 1.8],
    )
    assert scorecard.research_yield_pct == 0.0
    assert scorecard.research_value_added == 26  # (0*5) + (2*3) + (10*2) = 26 RVA
    assert scorecard.median_oos_sharpe == 1.1
    assert "Research Value:    + 26 RVA" in scorecard.summary()
