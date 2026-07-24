# Experiment: 2026-07-13-volatility-regime-replication-real

**id:** 2026-07-13-volatility-regime-replication
**title:** Replication of the volatility-regime timing strategy (vol_window=20, median_window=60, vol_multiple=1.0) on QQQ — an independent, predeclared dataset
**economic_rationale:** The volatility-regime timing mechanism identified on SPY (low-vol regime → long, high-vol regime → cash) should generalize to QQQ because volatility-regime persistence is a market-structural property, not instrument-specific. QQQ has higher average volatility than SPY but similar regime dynamics. This is a pure replication: no parameters are tuned, and the hypothesis was preregistered *after* the SPY result was frozen but *before* any QQQ results are observed. Replication success would strengthen the claim that the mechanism is structurally valid; failure would suggest the SPY result was instrument-specific.
**strategy_id:** volatility-regime
**strategy_params:** {'vol_window': 20, 'median_window': 60, 'vol_multiple': 1.0}
**instrument:** QQQ
**universe:** QQQ only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** Sharpe > 0.3 OOS (same threshold as original), Max drawdown < QQQ benchmark max drawdown OOS, Win rate > 40% OOS, Minimum 30 OOS trades (gate)
**failure_criteria:** Sharpe < 0 OOS, Strategy loses to buy-and-hold (QQQ) on risk-adjusted basis OOS, Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**expected_trade_frequency:** ~15-30 transitions/year (same regime dynamics as SPY)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** 
**status:** completed
**success:** YES
**data_digest:** 23fe75f0e6807ed153b4ae75b623cc5b0d0ce5402d724e74ca42d2790126eea7
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 01f733d69b5952899c65de3da3d3a1f64fb3a2b331b365058cd785ecd20a7ed4
**seed:** (no seed — real data)
**frozen_at:** 2026-07-13
**data_source:** yfinance

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 1.00% | 94.95% | 0.00% | 1.12% |
| CAGR | 0.50% | 39.90% | 0.00% | 0.56% |
| Sharpe Ratio | 1.0574 | 1.9640 | N/A | 1.0340 |
| Max Drawdown | 0.31% | 13.56% | 0.00% | 0.45% |
| Win Rate | 80.0% | N/A | N/A | 60.9% |
| Total Trades | 30 | 0 | 0 | 23 |

### Extended Metrics
- Turnover (total): 59.6%
- Time in market: 48.5%
- Longest flat period: 60 bars
- Buy-and-hold exposure-adjusted return: 46.05%
- Buy-and-hold exposure-adjusted max drawdown: 6.58%

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000)
- Mean PnL: 2012.41
- Median PnL: 1990.76
- Std PnL: 540.43
- 5th pctl: 1178.76
- 95th pctl: 2997.63

### Parameter Sensitivity (OOS)
- vol_window=20,median_window=60,vol_multiple=1.0: return=1.00%, sharpe=1.0574, dd=0.31%, trades=30

### Walk-Forward
- Windows: 15
- Mean Sharpe: 0.9088

### Gate
- Min trades: 30
- Actual trades: 30
- Passed: YES
- Reason: Trade count 30 >= minimum 30

**notes:** Gate: PASSED. OOS trade count: 30. Policy: Path A. Candidate vs BH return: 1.00% vs 94.95%. Block bootstrap 5th pctl: 1178.76.
