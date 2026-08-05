# Hypothesis: Volatility-regime timing replication on QQQ

**id:** 2026-07-13-volatility-regime-replication
**title:** Replication of the volatility-regime timing strategy (vol_window=20, median_window=60, vol_multiple=1.0) on QQQ — an independent, predeclared dataset
**economic_rationale:** The volatility-regime timing mechanism identified on SPY (low-vol regime → long, high-vol regime → cash) should generalize to QQQ because volatility-regime persistence is a market-structural property, not instrument-specific. QQQ has higher average volatility than SPY but similar regime dynamics. This is a pure replication: no parameters are tuned, and the hypothesis was preregistered *after* the SPY result was frozen but *before* any QQQ results are observed. Replication success would strengthen the claim that the mechanism is structurally valid; failure would suggest the SPY result was instrument-specific.
**strategy_id:** volatility-regime
**strategy_params:** vol_window=20, median_window=60, vol_multiple=1.0
**instrument:** QQQ
**universe:** QQQ only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**expected_trade_frequency:** ~15-30 transitions/year (same regime dynamics as SPY)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:**
**success_criteria:**
- Sharpe > 0.3 OOS (same threshold as original)
- Max drawdown < QQQ benchmark max drawdown OOS
- Win rate > 40% OOS
- Minimum 30 OOS trades (gate)
**failure_criteria:**
- Sharpe < 0 OOS
- Strategy loses to buy-and-hold (QQQ) on risk-adjusted basis OOS
- Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**notes:** Exact replication of SPY volatility-regime test (experiment 2026-07-13-volatility-regime, frozen at commit 3de8fa8). No parameters changed. Instrument changed from SPY to QQQ. Pooled trade count policy (knowledge/research/pooled-trade-count-policy.md) applies if future multi-instrument extensions are considered. No QQQ results have been observed at time of preregistration.
