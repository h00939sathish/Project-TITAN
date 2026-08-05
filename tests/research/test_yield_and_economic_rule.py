import pytest
from titan.research.experiment import Experiment
from titan.research.yield_tracker import ResearchHealthScorecard


def test_experiment_requires_economic_rationale():
    with pytest.raises(ValueError, match="Every new experiment must define a clear economic rationale"):
        Experiment(
            id="EXP-TEST",
            question="Does RSI work?",
            economic_rationale="",  # Empty!
            dataset_id="SPY",
            features=("rsi",),
            target="return",
        )


def test_experiment_accepts_valid_economic_rationale():
    exp = Experiment(
        id="EXP-TEST",
        question="Does opening imbalance predict intraday continuation?",
        economic_rationale="We believe institutions completing large opening orders create persistent intraday price pressure.",
        dataset_id="SPY",
        features=("opening_imbalance",),
        target="return_15m",
    )
    assert exp.economic_rationale.startswith("We believe")


def test_research_yield_calculation():
    tracker = ResearchHealthScorecard(
        experiments_run=42,
        rejected=34,
        refined=6,
        promoted=2,
    )
    assert tracker.research_yield_pct == 4.76
    assert "Research Yield:      4.8%" in tracker.summary()
