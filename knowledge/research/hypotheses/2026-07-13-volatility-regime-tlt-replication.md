# Hypothesis: Volatility-regime timing replication on TLT

**id:** 2026-07-13-volatility-regime-tlt-replication
**title:** Cross-asset replication of volatility-regime timing on TLT with unchanged parameters
**economic_rationale:** The volatility-regime mechanism should be tested outside US equity beta before any claim of generality. TLT is selected before observing its strategy results because it represents a different asset class and duration-driven return source. This is an exact parameter replication, not an optimization exercise.
**strategy_id:** volatility-regime
**strategy_params:** vol_window=20, median_window=60, vol_multiple=1.0
**instrument:** TLT
**universe:** TLT only; no pooled portfolio
**calendar:** 2020-01-02 to 2024-12-31, subject to fixture-quality and entitlement checks
**train_period:** 2020-01-02 to 2022-12-31
**test_period:** 2023-01-01 to 2024-12-31
**expected_trade_frequency:** 15-40 OOS transitions, based on daily volatility-regime changes
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:**
**success_criteria:**
- Sharpe > 0.3 OOS
- Max drawdown < TLT buy-and-hold benchmark max drawdown OOS
- Win rate > 40% OOS
- Minimum 30 OOS trades
**failure_criteria:**
- Sharpe < 0 OOS
- Strategy loses to TLT buy-and-hold on risk-adjusted basis OOS
- Fewer than 30 OOS trades without preregistered Path B evidence
**costs:** 1.0 bps commission, 0.5 bps slippage; corporate-action adjustments applied through the standard data pipeline
**data_eligibility:** A versioned, CA-adjusted daily TLT fixture must pass manifest, session, duplicate, and corporate-action checks. The OOS daily-return correlation against both frozen SPY and QQQ fixtures must be measured and stored before the strategy is run. A correlation above 0.30 does not permit pooling; this study remains a standalone replication in all cases.
**notes:** The SPY and QQQ volatility-regime records are frozen. This study preserves their strategy parameters and Path A acceptance rules. Its result is assessed independently and cannot change a frozen experiment. No TLT fixture or TLT strategy result has been observed when this hypothesis is registered.
