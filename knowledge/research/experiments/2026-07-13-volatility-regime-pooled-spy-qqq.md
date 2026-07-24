# Experiment: 2026-07-13-volatility-regime-pooled-spy-qqq

**id:** 2026-07-13-volatility-regime-pooled-spy-qqq
**title:** Pooled volatility-regime timing on SPY+QQQ
**economic_rationale:** Pooled test of volatility-regime timing across two highly correlated US equity indices. Uses the pooled-trade-count policy to discount effective trades for cross-instrument correlation.
**strategy_id:** volatility-regime
**strategy_params:** {'vol_window': 20, 'median_window': 60, 'vol_multiple': 1.0}
**data_digest:** e9506756a1e3fbe35701d2521b89cf8d61326e730eafa577003889c70a1d9202
**code_digest:** 3de8fa8
**config_digest:** 6c6f507ed1cc57cd03a589d15adda2e0b8977901999333e3dd28ebd057274a8e
**seed:** 42
**frozen_at:** 2026-07-13
**instrument:** SPY+QQQ
**universe:** SPY, QQQ
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** Sharpe > 0.3 OOS, Max drawdown < SPY benchmark max drawdown OOS
**failure_criteria:** Sharpe < 0 OOS
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**expected_trade_frequency:** ~30-60 transitions/year (combined)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** 
**status:** completed
**success:** YES

## Results

### Per-Instrument (OOS)

- SPY: 24 trades, return 1.05%, Sharpe 1.4592, max DD 0.13%, win rate 75.0%
- QQQ: 37 trades, return 0.65%, Sharpe 0.6301, max DD 0.22%, win rate 64.9%

### Pooled Equity Metrics (OOS)

- Total Return: 0.85%
- Sharpe Ratio: 1.3542
- Max Drawdown: 0.11%
- Buy-and-Hold (pooled) Return: 73.49%

### Pairwise Correlations

- SPY vs QQQ: r=-0.0347 (n=519)

### Trade Accounting

- Raw total trades: 61
- Average pairwise correlation: -0.0347
- Effective trades (discounted): 61.0
- Per-instrument distribution: SPY=24, QQQ=37

### Gate

- Min trades: 30
- Effective trades: 61
- Passed: YES
- Reason: Trade count 61 >= minimum 30

**notes:** Gate: PASSED. Effective OOS trades: 61. Raw trades: 61. Avg pairwise corr: -0.0347. Pooled Sharpe: 1.3542. Pooled return: 0.85%.
