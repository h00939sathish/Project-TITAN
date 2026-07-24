# Experiment: ma-crossover-baseline-001

**id:** ma-crossover-baseline-001
**hypothesis:** A 5/20-day moving average crossover on SPY generates positive risk-adjusted returns after costs
**owner:** TITAN Development
**data_digest:** 94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 96a899e24d9b48e6ba8b878c155816b2a11b85b6b986b4554a5c2901549d945d
**seed:** 42
**frozen_at:** 2026-07-13
**calendar:** 2020-01-02T00:00:00 to 2024-12-31T00:00:00
**universe:** SPY only
**success_criteria:** Sharpe > 0.5 OOS, max DD < SPY benchmark, win rate > 40%
**failure_criteria:** Sharpe < 0 OOS, or strategy loses to benchmark on risk-adjusted basis
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()

## Results

### Out-of-Sample (2023-01-01+)

| Metric | Baseline (MA 5,20) | Benchmark (BH) |
|---|---|---|
| Total Return | 1.71% | 59.17% |
| Sharpe Ratio | 1.5583 | 1.8806 |
| Max Drawdown | 0.30% | 2.62% |
| Win Rate | 30.8% | N/A |
| Volatility (ann.) | 0.53% | N/A |
| Calmar Ratio | 5.6813 | N/A |
| Profit Factor | 10.5377 | N/A |
| Total Trades | 13 | 0 |

### Full Period

| Metric | Baseline (MA 5,20) | Benchmark (BH) |
|---|---|---|
| Total Return | 3.76% | 92.84% |
| Sharpe Ratio | 1.6884 | 0.9857 |
| Max Drawdown | 0.34% | 38.42% |

### Walk-Forward (OOS)
- Windows: 4
- Mean OOS Sharpe: 1.0464

### Parameter Perturbation (OOS)
| Variant | Return | Sharpe | Max DD |
|---|---|---|---|
| fast=4, slow=20 | 0.79% | 0.8921 | 0.21% |
| fast=6, slow=20 | 1.82% | 1.6732 | 0.24% |
| fast=5, slow=19 | 1.57% | 1.4527 | 0.30% |
| fast=5, slow=21 | 0.94% | 1.0634 | 0.21% |

### Monte Carlo (1000 sims, OOS trades)
- Mean PnL: 1717.03
- Median PnL: 1699.41
- Std PnL: 1152.27
- 5th pctl: -250.47
- 95th pctl: 3710.29

### Slippage Stress (OOS)
| Multiplier | Return | Sharpe | Max DD |
|---|---|---|---|
| 0.5x | 1.71% | 1.5598 | 0.30% |
| 1x | 1.71% | 1.5583 | 0.30% |
| 2x | 1.70% | 1.5556 | 0.30% |
| 5x | 1.70% | 1.5471 | 0.31% |

**reviewer:** (pending)
**disposition:** rejected
**notes:** Success criteria not met on OOS period. Results are synthetic-fixture estimates.
