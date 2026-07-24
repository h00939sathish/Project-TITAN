# Experiment: 2026-07-13-momentum-qqq-replication

**id:** 2026-07-13-momentum-qqq-replication
**title:** Replication of 20-day time-series momentum on QQQ — an independent, predeclared dataset
**economic_rationale:** Time-series momentum should generalize across US equity ETFs because trend persistence is a market-structural property. QQQ (Nasdaq-100) has stronger trends than SPY but also higher volatility and sharper reversals, providing a more demanding test. This is a pure replication with unchanged parameters, preregistered before any QQQ momentum results are observed.
**strategy_id:** time-series-momentum
**strategy_params:** {'lookback': 20}
**instrument:** QQQ
**universe:** QQQ only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** 
**failure_criteria:** 
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**expected_trade_frequency:** ~10-20 transitions/year (same as SPY)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** **success_criteria:
Sharpe > 0.3 OOS
Max drawdown < QQQ benchmark max drawdown OOS
Win rate > 40% OOS
Minimum 30 OOS trades (gate)
**failure_criteria:
Sharpe < 0 OOS
Strategy loses to buy-and-hold (QQQ) on risk-adjusted basis OOS
Fewer than 30 OOS trades without documented override reason
**status:** completed
**success:** YES

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 1.26% | 94.95% | 0.00% | 1.12% |
| CAGR | 0.63% | 39.90% | 0.00% | 0.56% |
| Sharpe Ratio | 1.0454 | 1.9640 | N/A | 1.0340 |
| Max Drawdown | 0.73% | 13.56% | 0.00% | 0.45% |
| Win Rate | 36.4% | N/A | N/A | 60.9% |
| Total Trades | 33 | 0 | 0 | 23 |

### Extended Metrics
- Turnover (total): 67.7%
- Time in market: 74.0%
- Longest flat period: 20 bars
- Buy-and-hold exposure-adjusted return: 70.31%
- Buy-and-hold exposure-adjusted max drawdown: 10.04%

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000)
- Mean PnL: 1924.77
- Median PnL: 1963.35
- Std PnL: 987.81
- 5th pctl: 275.96
- 95th pctl: 3512.34

### Parameter Sensitivity (OOS)
- lookback=20: return=1.26%, sharpe=1.0454, dd=0.73%, trades=33

### Walk-Forward
- Windows: 15
- Mean Sharpe: 0.8129

### Gate
- Min trades: 30
- Actual trades: 33
- Passed: YES
- Reason: Trade count 33 >= minimum 30

**notes:** Gate: PASSED. OOS trade count: 33. Policy: Path A. Candidate vs BH return: 1.26% vs 94.95%. Block bootstrap 5th pctl: 275.96.
