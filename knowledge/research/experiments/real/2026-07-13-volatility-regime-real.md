# Experiment: 2026-07-13-volatility-regime-real

**id:** 2026-07-13-volatility-regime
**title:** A volatility-regime timing strategy on SPY — long when short-term vol is below its longer-term median — generates positive risk-adjusted returns with sufficient OOS trades
**economic_rationale:** Volatility regimes exhibit persistence. Low-volatility periods tend to coincide with trending, higher-Sharpe environments; high-volatility periods are associated with uncertainty, reversals, and tail risk. By entering long only when 20-day rolling vol is below the 60-day median of that measure, the strategy times equity exposure based on the volatility regime rather than predicting price direction. This is a risk-regime-awareness strategy — economically distinct from both momentum/trend-following (MA crossover) and counter-trend (mean reversion). It does not attempt to forecast price movements; it attempts to avoid unfavorable risk regimes.
**strategy_id:** volatility-regime
**strategy_params:** {'vol_window': 20, 'median_window': 60, 'vol_multiple': 1.0}
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** Sharpe > 0.3 OOS, Max drawdown < SPY benchmark max drawdown OOS, Win rate > 40% OOS, Minimum 30 OOS trades (gate)
**failure_criteria:** Sharpe < 0 OOS, Strategy loses to buy-and-hold on risk-adjusted basis OOS, Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**expected_trade_frequency:** ~15-30 transitions/year (regime changes several times per year)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** 
**status:** completed
**success:** NO
**data_digest:** 1274f3c100479dc6712924a7ae9528a701d412c069cf6895e540c9c95ab4ec2d
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 01f733d69b5952899c65de3da3d3a1f64fb3a2b331b365058cd785ecd20a7ed4
**seed:** (no seed — real data)
**frozen_at:** 2026-07-13
**data_source:** yfinance

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.85% | 60.27% | 0.00% | 1.17% |
| CAGR | 0.42% | 26.78% | 0.00% | 0.59% |
| Sharpe Ratio | 1.0600 | 1.8826 | N/A | 1.2902 |
| Max Drawdown | 0.30% | 10.11% | 0.00% | 0.39% |
| Win Rate | 50.0% | N/A | N/A | 50.0% |
| Total Trades | 24 | 0 | 0 | 24 |

### Extended Metrics
- Turnover (total): 61.3%
- Time in market: 50.9%
- Longest flat period: 65 bars
- Buy-and-hold exposure-adjusted return: 30.68%
- Buy-and-hold exposure-adjusted max drawdown: 5.15%

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000)
- Mean PnL: 1731.94
- Median PnL: 1749.12
- Std PnL: 1195.05
- 5th pctl: -284.26
- 95th pctl: 3626.17

### Parameter Sensitivity (OOS)
- vol_window=20,median_window=60,vol_multiple=1.0: return=0.85%, sharpe=1.0600, dd=0.30%, trades=24

### Walk-Forward
- Windows: 15
- Mean Sharpe: 0.4561

### Gate
- Min trades: 30
- Actual trades: 24
- Passed: NO
- Reason: Trade count 24 below minimum 30. Provide a documented reason at override_doc to accept a low-turnover strategy.

**notes:** Gate: FAILED. OOS trade count: 24. Policy: Path A. Candidate vs BH return: 0.85% vs 60.27%. Block bootstrap 5th pctl: -284.26.
