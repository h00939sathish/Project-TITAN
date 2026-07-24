# Experiment: 2026-07-13-volatility-regime-tlt-replication-real

**id:** 2026-07-13-volatility-regime-tlt-replication
**title:** Cross-asset replication of volatility-regime timing on TLT with unchanged parameters
**economic_rationale:** The volatility-regime mechanism should be tested outside US equity beta before any claim of generality. TLT is selected before observing its strategy results because it represents a different asset class and duration-driven return source. This is an exact parameter replication, not an optimization exercise.
**strategy_id:** volatility-regime
**strategy_params:** {'vol_window': 20, 'median_window': 60, 'vol_multiple': 1.0}
**instrument:** TLT
**universe:** TLT only; no pooled portfolio
**calendar:** 2020-01-02 to 2024-12-31, subject to fixture-quality and entitlement checks
**train_period:** 2020-01-02 to 2022-12-31
**test_period:** 2023-01-01 to 2024-12-31
**success_criteria:** Sharpe > 0.3 OOS, Max drawdown < TLT buy-and-hold benchmark max drawdown OOS, Win rate > 40% OOS, Minimum 30 OOS trades
**failure_criteria:** Sharpe < 0 OOS, Strategy loses to TLT buy-and-hold on risk-adjusted basis OOS, Fewer than 30 OOS trades without preregistered Path B evidence
**costs:** 1.0 bps commission, 0.5 bps slippage; corporate-action adjustments applied through the standard data pipeline
**expected_trade_frequency:** 15-40 OOS transitions, based on daily volatility-regime changes
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** 
**status:** completed
**success:** NO
**data_digest:** 96ae964838d1dfef435ebb0d323c2c8d776a04f70d6c5d30e6bb2a073685f78b
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 01f733d69b5952899c65de3da3d3a1f64fb3a2b331b365058cd785ecd20a7ed4
**seed:** (no seed — real data)
**frozen_at:** 2026-07-13
**data_source:** yfinance

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | -0.08% | -13.46% | 0.00% | -0.11% |
| CAGR | -0.04% | -7.02% | 0.00% | -0.06% |
| Sharpe Ratio | -0.3839 | -0.3620 | N/A | -0.5889 |
| Max Drawdown | 0.12% | 23.81% | 0.00% | 0.16% |
| Win Rate | 32.0% | N/A | N/A | 14.3% |
| Total Trades | 25 | 0 | 0 | 28 |

### Extended Metrics
- Turnover (total): 12.5%
- Time in market: 44.7%
- Longest flat period: 66 bars
- Buy-and-hold exposure-adjusted return: -6.02%
- Buy-and-hold exposure-adjusted max drawdown: 10.64%

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000)
- Mean PnL: -141.80
- Median PnL: -131.99
- Std PnL: 136.10
- 5th pctl: -387.44
- 95th pctl: 74.85

### Parameter Sensitivity (OOS)
- vol_window=20,median_window=60,vol_multiple=1.0: return=-0.08%, sharpe=-0.3839, dd=0.12%, trades=25

### Walk-Forward
- Windows: 15
- Mean Sharpe: -0.8281

### Gate
- Min trades: 30
- Actual trades: 25
- Passed: NO
- Reason: Trade count 25 below minimum 30. Provide a documented reason at override_doc to accept a low-turnover strategy.

**notes:** Gate: FAILED. OOS trade count: 25. Policy: Path A. Candidate vs BH return: -0.08% vs -13.46%. Block bootstrap 5th pctl: -387.44.
