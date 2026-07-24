# Experiment: 2026-07-13-mean-reversion

**id:** 2026-07-13-mean-reversion
**title:** A 20-day z-score mean-reversion strategy on SPY generates positive risk-adjusted returns after costs, with sufficient OOS trades for statistical confidence
**economic_rationale:** Short-term price dislocations (z-score below -2.0, i.e. >2 std dev below 20-day mean) capture intra-trend overreactions that historically revert. This is a counter-trend strategy — fundamentally different from the momentum/trend-following hypotheses tested so far. The 20-day window provides a balance between capturing short-term bounces and avoiding micro-structure noise. Exit at z-score > -0.5 locks in the reversion while limiting re-exposure risk.
**strategy_params:** {'window': 20, 'entry_z': -2.0, 'exit_z': -0.5}
**data_digest:** 94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 7e32ae64724496a0860893fcce98ea7a0dc4152e020bba7d5eb69bea4050cbbe
**seed:** 42
**frozen_at:** 2026-07-13
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** Sharpe > 0.3 OOS, Max drawdown < SPY benchmark max drawdown OOS, Win rate > 40% OOS, Minimum 30 OOS trades (gate)
**failure_criteria:** Sharpe < 0 OOS, Strategy loses to buy-and-hold on risk-adjusted basis OOS, Fewer than 30 OOS trades without documented override reason
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**status:** completed
**success:** NO

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.11% | 59.17% | 0.00% | 1.71% |
| Sharpe Ratio | 0.6920 | 1.8806 | N/A | 1.5583 |
| Max Drawdown | 0.00% | 2.62% | 0.00% | 0.30% |
| Win Rate | 100.0% | N/A | N/A | 30.8% |
| Total Trades | 2 | 0 | 0 | 13 |

### Extended Metrics
- Turnover (total): 4.3%
- Time in market: 0.2%
- Longest flat period: 269 bars

### Block Bootstrap (OOS)
- Method: simple_resample — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence (only 2 trades, so degenerate)
- Mean PnL (USD): 0.00
- Median PnL (USD): 0.00
- Std PnL (USD): 0.00
- 5th pctl (USD): 0.00
- 95th pctl (USD): 0.00

### Parameter Sensitivity (OOS)
- window=18,entry_z=-2.0,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=19,entry_z=-2.0,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-1.7,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-1.9,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.0,exit_z=-0.2: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.0,exit_z=-0.4: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.0,exit_z=-0.6: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.0,exit_z=-0.8: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.1,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=20,entry_z=-2.3,exit_z=-0.5: return=0.00%, sharpe=0.0000, dd=0.00%, trades=0
- window=21,entry_z=-2.0,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2
- window=22,entry_z=-2.0,exit_z=-0.5: return=0.11%, sharpe=0.6920, dd=0.00%, trades=2

### Walk-Forward
- Windows: 16
- Mean Sharpe: -0.2495

### Gate
- Min trades: 30
- Actual trades: 2
- Passed: NO
- Reason: Trade count 2 below minimum 30. Provide a documented reason at override_doc to accept a low-turnover strategy.

**disposition:** rejected
**disposition_reason:** Gate failure — only 2 OOS trades (minimum 30 required). Without a preregistered Path B override rationale, the strategy cannot be evaluated for statistical significance.

**notes:** Gate: FAILED. OOS trade count: 2. Candidate vs BH return: 0.11% vs 59.17%. Block bootstrap 5th pctl: 0.00. The z-score entry threshold of -2.0 generates too few signals on SPY (2 in 520 trading days). All 2 trades were profitable (100% win rate, 0.11% return total, Sharpe 0.692) but the sample is far too small for any statistical conclusion. Walk-forward mean Sharpe was -0.2495 (negative), further suggesting the strategy does not generalize. Future variant with a less strict threshold (e.g., entry_z=-1.5) could generate more signals but would constitute a new hypothesis requiring fresh preregistration.
