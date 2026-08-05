# Hypothesis: Short-term mean reversion on SPY

**id:** 2026-07-13-mean-reversion
**title:** A 20-day z-score mean-reversion strategy on SPY generates positive risk-adjusted returns after costs, with sufficient OOS trades for statistical confidence
**economic_rationale:** Short-term price dislocations (z-score below -2.0, i.e. >2 std dev below 20-day mean) capture intra-trend overreactions that historically revert. This is a counter-trend strategy — fundamentally different from the momentum/trend-following hypotheses tested so far. The 20-day window provides a balance between capturing short-term bounces and avoiding micro-structure noise. Exit at z-score > -0.5 locks in the reversion while limiting re-exposure risk.
**strategy_params:** window=20, entry_z=-2.0, exit_z=-0.5
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**strategy_id:** mean-reversion
**expected_trade_frequency:** ~2 trades/year (z=-2.0 is a rare threshold)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:**
**success_criteria:**
- Sharpe > 0.3 OOS
- Max drawdown < SPY benchmark max drawdown OOS
- Win rate > 40% OOS
- Minimum 30 OOS trades (gate)
**failure_criteria:**
- Sharpe < 0 OOS
- Strategy loses to buy-and-hold on risk-adjusted basis OOS
- Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**notes:** Preregistered before any OOS results are known. No parameter tuning based on prior experiments. This is the first counter-trend hypothesis tested — distinctive from the MA crossover families (trend-following momentum and long-term trend proxy).

