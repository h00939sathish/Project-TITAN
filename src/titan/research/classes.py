"""Hypothesis Classes — organizes experiments by economic mechanism.

Every experiment belongs to one family. This makes the research narrative
about "what have we learned about momentum?" rather than "what did indicator
X return?"
"""
from __future__ import annotations

from enum import Enum
from titan.research.experiment import Experiment


class HypothesisClass(str, Enum):
    """Taxonomy of economic mechanisms this platform investigates."""

    TREND = "trend"                     # Do trends persist? (momentum, MA cross, etc.)
    MEAN_REVERSION = "mean_reversion"   # Do extremes reverse? (RSI, bollinger, etc.)
    CROSS_SECTIONAL = "cross_sectional" # Do winners keep winning? (relative strength)
    SECTOR_ROTATION = "sector_rotation" # Does sector leadership persist?
    VOLATILITY = "volatility"           # Does volatility predict returns? (ATR, VIX)
    EXECUTION = "execution"             # Does implementation detail matter?
    REGIME = "regime"                   # Does regime state affect other signals?
    CALENDAR = "calendar"               # Do calendar effects exist? (day-of-week, month)
    FUNDAMENTAL = "fundamental"         # Do fundamentals predict returns?
    MACRO = "macro"                     # Do macro variables predict returns?


# Metadata mapping for each class
CLASS_DESCRIPTIONS = {
    HypothesisClass.TREND: "Tests whether directional price movements persist over time.",
    HypothesisClass.MEAN_REVERSION: "Tests whether extreme price movements revert toward均值.",
    HypothesisClass.CROSS_SECTIONAL: "Tests whether relative outperformance predicts future outperformance.",
    HypothesisClass.SECTOR_ROTATION: "Tests whether leading/lagging sectors persist.",
    HypothesisClass.VOLATILITY: "Tests whether volatility regime predicts subsequent returns.",
    HypothesisClass.EXECUTION: "Tests whether implementation choices (sizing, timing) affect outcomes.",
    HypothesisClass.REGIME: "Tests whether market regime modulates other signal efficacy.",
    HypothesisClass.CALENDAR: "Tests whether time-based patterns (day, month, holiday) predict returns.",
    HypothesisClass.FUNDAMENTAL: "Tests whether fundamental metrics (earnings, value) predict returns.",
    HypothesisClass.MACRO: "Tests whether macro indicators (rates, inflation) predict returns.",
}


def classify(experiment: Experiment, cls: HypothesisClass) -> Experiment:
    """Tag an experiment with its hypothesis class.

    Usage:
        exp = classify(exp, HypothesisClass.TREND)
    """
    # Store in params so it travels with the experiment fingerprint
    updated_params = dict(experiment.params)
    updated_params["hypothesis_class"] = cls.value
    return Experiment(
        id=experiment.id,
        question=experiment.question,
        dataset_id=experiment.dataset_id,
        features=experiment.features,
        target=experiment.target,
        filter_expr=experiment.filter_expr,
        params=updated_params,
        created_at=experiment.created_at,
    )
