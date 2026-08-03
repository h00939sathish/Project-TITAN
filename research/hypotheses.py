"""Hypothesis definitions organized by economic class.

Each hypothesis belongs to a HypothesisClass. This lets TITAN answer
"what have we learned about momentum?" rather than "what did indicator X return?"
"""
from __future__ import annotations

from titan.research.experiment import Experiment
from titan.research.classes import HypothesisClass, classify


def h(cls: HypothesisClass, **kw) -> Experiment:
    """Shorthand: create an experiment and classify it in one call."""
    return classify(Experiment(**kw), cls)


hypotheses = [

    # ── TREND: Momentum Persistence After Vol Contraction ──────────────
    h(HypothesisClass.TREND,
      id="EXP-00002",
      question="Does momentum persist after volatility contraction? "
               "Cross-sectional: rank by 60-day return, filter by low ATR percentile, "
               "measure 20-day forward return spread between top and bottom quintiles.",
      dataset_id="equity_etf_universe_v1",
      features=("return_60d", "atr_percentile_20", "vol_contraction_flag"),
      target="forward_return_20d",
      filter_expr="vol_contraction_flag == True",
    ),

    # ── CROSS-SECTIONAL: Relative Strength After Market Weakness ───────
    h(HypothesisClass.CROSS_SECTIONAL,
      id="EXP-00003",
      question="Do stocks with strong relative strength outperform after "
               "broad market weakness (SPY negative 5d return)? "
               "Cross-sectional: rank universe by 20d relative strength vs SPY, "
               "filter by SPY 5d return < 0, measure 10d forward spread.",
      dataset_id="equity_etf_universe_v1",
      features=("relative_strength_20d", "return_5d", "vol_contraction_flag"),
      target="forward_return_10d",
      filter_expr="return_5d < 0",
    ),

    # ── SECTOR ROTATION: Sector Leadership Persistence ─────────────────
    h(HypothesisClass.SECTOR_ROTATION,
      id="EXP-00004",
      question="Do sector ETFs that led the market in the past 20 days "
               "continue to lead in the next 20 days? "
               "Cross-sectional: rank sector ETFs by 20d return, "
               "measure top-decile vs bottom-decile forward spread.",
      dataset_id="sector_etf_universe_v1",
      features=("return_20d", "realized_vol_20"),
      target="forward_return_20d",
    ),

    # ── MEAN REVERSION: High Volatility → Reversion ───────────────────
    h(HypothesisClass.MEAN_REVERSION,
      id="EXP-00005",
      question="Do assets mean-revert after periods of extreme volatility? "
               "Cross-sectional: rank by realized_vol_20 percentile (top quintile = highest vol), "
               "measure 20-day forward return. Expect negative IC (high vol → reverts downward).",
      dataset_id="equity_etf_universe_v1",
      features=("realized_vol_20", "return_20d", "atr_percentile_20"),
      target="forward_return_20d",
      filter_expr="realized_vol_20 > 0.8",
    ),

    # ── EXECUTION: Exact Replica of Live MA Crossover ──────────────────
    h(HypothesisClass.EXECUTION,
      id="EXP-00006",
      question="Does TITAN's live MA crossover strategy (EMA 5/20) have "
               "statistically significant predictive power for 20-day forward returns? "
               "This is NOT an approximation. Uses the exact same EMA(5) × EMA(20) "
               "logic as the running paper session.",
      dataset_id="spy_daily_v1",
      features=("ema_crossover_signal",),
      target="forward_return_20d",
    ),

]
