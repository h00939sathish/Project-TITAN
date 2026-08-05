# Hypothesis: Volatility-regime timing on SPY

**id:** 2026-07-13-volatility-regime
**title:** A volatility-regime timing strategy on SPY — long when short-term vol is below its longer-term median — generates positive risk-adjusted returns with sufficient OOS trades
**economic_rationale:** Volatility regimes exhibit persistence. Low-volatility periods tend to coincide with trending, higher-Sharpe environments; high-volatility periods are associated with uncertainty, reversals, and tail risk. By entering long only when 20-day rolling vol is below the 60-day median of that measure, the strategy times equity exposure based on the volatility regime rather than predicting price direction. This is a risk-regime-awareness strategy — economically distinct from both momentum/trend-following (MA crossover) and counter-trend (mean reversion). It does not attempt to forecast price movements; it attempts to avoid unfavorable risk regimes.
**strategy_id:** volatility-regime
**strategy_params:** vol_window=20, median_window=60, vol_multiple=1.0
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**expected_trade_frequency:** ~15-30 transitions/year (regime changes several times per year)
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
**notes:** Preregistered before any OOS results are known. No parameter tuning based on prior experiments. This is the first volatility-regime strategy tested — distinct from both trend-following and counter-trend families. The 20/60-day window pair is chosen to match the typical persistence length of vol regimes (3 months of daily data for the median reference). vol_multiple=1.0 means the entry/exit threshold is exactly the median — a neutral starting point.
