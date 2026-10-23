"""Hypothesis definitions organized by economic class.

Each hypothesis belongs to a HypothesisClass. This lets TITAN answer
"what have we learned about momentum?" rather than "what did indicator X return?"

`titan research run <EXP-id>` reads this file. A hypothesis is a WF-v2 candidate only
if it carries params["wf_v2"] (see titan.research.wf_v2.parse_spec for the keys).
"""
from __future__ import annotations

from titan.research.experiment import Experiment
from titan.research.classes import HypothesisClass, classify


def h(cls: HypothesisClass, **kw) -> Experiment:
    """Shorthand: create an experiment and classify it in one call."""
    return classify(Experiment(**kw), cls)


hypotheses = [

    # ── VOLATILITY: Vol-Weighted Carry (successor to rejected EXP-00023) ─
    h(HypothesisClass.VOLATILITY,
      id="EXP-00024",
      question="Does inverse-volatility weighting rescue G10 carry after costs? "
               "EXP-00023 (monthly G10 carry, 2018-07..2026-06) was REJECTED: "
               "only mechanical accrual (+0.18%/mo, t=1.14, win 57%, maxDD "
               "-13.5%) with no UIP spot anomaly. EXP-00024 scales carry "
               "exposure by 1/max(sigma_t, 0.05) with weekly (not monthly) "
               "rebalancing and asks whether risk-adjusted yield survives "
               "10bps costs and cuts drawdown >=40% vs the naive baseline.",
      economic_rationale="Carry accrual is stable mechanical yield but naive "
               "long-high/short-low exposure is consumed by turnover and "
               "left-tail crashes (EXP-00023, regime-compressed post-2008). "
               "Volatility-scaling de-leverages during stress when carry "
               "trades crash; if it cannot beat EXP-00023's baseline (t=1.14, "
               "maxDD -13.5%) on OOS net Sharpe and drawdown, the vol-carry "
               "hypothesis is falsified for this universe.",
      dataset_id="fx_carry_rates_v1",
      features=("rate_differential_t2", "realized_vol_21d", "vol_floor_0p05"),
      target="forward_carry_adj_return_1w",
      params={"expected_sign": 1.0, "rebalance": "weekly_wed_17utc",
              "cost_bps": 10, "tenor": "1W", "baseline": "EXP-00023"},
    ),

    # ── TREND: registered trader.dev F1 candidate, first honest OOS ──────
    h(HypothesisClass.TREND,
      id="EXP-00033",
      question="Does the registered traderdev-ema9-vwap candidate keep a positive, "
               "cost-surviving edge on data it was never tuned on? EXP-00025 found "
               "the F1 family net positive at 4h on EURUSD + GBPUSD (+408.3 pips "
               "pooled) but only over the 12 months the port was tuned on, and the "
               "promotion gate recorded walk_forward as UNMET for that reason. The "
               "2D surface has no compact plateau and the two pairs favour different "
               "corners. WF-v2 runs the frozen parameters over 2022-08..2025-07.",
      economic_rationale="A short-EMA cross of a volume-weighted price tracks the "
               "direction in which traded volume has recently been leaning, so it "
               "should capture persistent flow after a policy-rate turn rather than "
               "before it. If the EURUSD/GBPUSD result in EXP-00025 were real trend "
               "persistence it must reappear on unseen years; if it were the "
               "pair-specific surface noise the sensitivity sweep found, it must not. "
               "Either answer is decisive for TITAN's only registered candidate.",
      dataset_id="dukascopy_1m_ba_prior",
      features=("close", "high", "low", "volume"),
      target="next_bar_return",
      params={"wf_v2": {
          "strategy_id": "traderdev-ema9-vwap",
          "strategy_params": {"ema_period": 9, "vwap_period": 120,
                              "atr_period": 14, "trail_mult": 2.0},
          "instruments": ["EURUSD", "GBPUSD"],
          "timeframe_minutes": 240,
          "window": ["2022-08", "2025-07"],
          "position_mode": "long_short",
          "evidence_record": "research/evidence/EXP-00033.json",
      }},
    ),

]


# Written before Experiment required an economic rationale; constructing them raises.
# Kept as data so their questions are not lost. Add a rationale and move one into
# `hypotheses` to make it runnable.
LEGACY_WITHOUT_RATIONALE = [
    dict(cls=HypothesisClass.TREND,
         id="EXP-00002",
         question="Does momentum persist after volatility contraction? "
                  "Cross-sectional: rank by 60-day return, filter by low ATR percentile, "
                  "measure 20-day forward return spread between top and bottom quintiles.",
         dataset_id="equity_etf_universe_v1",
         features=("return_60d", "atr_percentile_20", "vol_contraction_flag"),
         target="forward_return_20d",
         filter_expr="vol_contraction_flag == True"),
    dict(cls=HypothesisClass.CROSS_SECTIONAL,
         id="EXP-00003",
         question="Do stocks with strong relative strength outperform after "
                  "broad market weakness (SPY negative 5d return)? "
                  "Cross-sectional: rank universe by 20d relative strength vs SPY, "
                  "filter by SPY 5d return < 0, measure 10d forward spread.",
         dataset_id="equity_etf_universe_v1",
         features=("relative_strength_20d", "return_5d", "vol_contraction_flag"),
         target="forward_return_10d",
         filter_expr="return_5d < 0"),
    dict(cls=HypothesisClass.SECTOR_ROTATION,
         id="EXP-00004",
         question="Do sector ETFs that led the market in the past 20 days "
                  "continue to lead in the next 20 days? "
                  "Cross-sectional: rank sector ETFs by 20d return, "
                  "measure top-decile vs bottom-decile forward spread.",
         dataset_id="sector_etf_universe_v1",
         features=("return_20d", "realized_vol_20"),
         target="forward_return_20d"),
    dict(cls=HypothesisClass.MEAN_REVERSION,
         id="EXP-00005",
         question="Do assets mean-revert after periods of extreme volatility? "
                  "Cross-sectional: rank by realized_vol_20 percentile (top quintile = highest vol), "
                  "measure 20-day forward return. Expect negative IC (high vol → reverts downward).",
         dataset_id="equity_etf_universe_v1",
         features=("realized_vol_20", "return_20d", "atr_percentile_20"),
         target="forward_return_20d",
         filter_expr="realized_vol_20 > 0.8"),
    dict(cls=HypothesisClass.EXECUTION,
         id="EXP-00006",
         question="Does TITAN's live MA crossover strategy (EMA 5/20) have "
                  "statistically significant predictive power for 20-day forward returns? "
                  "This is NOT an approximation. Uses the exact same EMA(5) × EMA(20) "
                  "logic as the running paper session.",
         dataset_id="spy_daily_v1",
         features=("ema_crossover_signal",),
         target="forward_return_20d"),
]
