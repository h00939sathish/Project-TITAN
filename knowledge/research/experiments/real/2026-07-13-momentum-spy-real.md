# Experiment: 2026-07-13-momentum-spy-real

**id:** 2026-07-13-momentum-spy
**title:** A 20-day time-series momentum strategy on SPY generates positive risk-adjusted returns after costs
**economic_rationale:** Time-series momentum captures persistent directional trends by going long when the N-day return is positive and short when negative. This is economically distinct from both the MA crossover (which uses two moving averages and only goes long) and mean reversion (which bets against the trend). Time-series momentum can profit from both uptrends and downtrends. The 20-day lookback balances sensitivity (captures short-term trends) with noise reduction.
**strategy_id:** time-series-momentum
**strategy_params:** {'lookback': 20}
**instrument:** SPY
**universe:** SPY only
**calendar:** 2020-01-02 to 2024-12-31
**train_period:** 2020-01-02
**test_period:** 2023-01-01
**success_criteria:** 
**failure_criteria:** 
**costs:** 1.0 bps commission, 0.5 bps slippage; CA-adjusted dividends via common_adjustments()
**expected_trade_frequency:** ~10-20 transitions/year (trend changes several times per year)
**sample_adequacy_policy:** Path A
**path_b_evidence_standard:** **success_criteria:
Sharpe > 0.3 OOS
Max drawdown < SPY benchmark max drawdown OOS
Win rate > 40% OOS
Minimum 30 OOS trades (gate)
**failure_criteria:
Sharpe < 0 OOS
Strategy loses to buy-and-hold (SPY) on risk-adjusted basis OOS
Fewer than 30 OOS trades without documented override reason
**status:** completed
**success:** YES
**data_digest:** 1274f3c100479dc6712924a7ae9528a701d412c069cf6895e540c9c95ab4ec2d
**code_digest:** 3de8fa8cc92dfbc416befb1da72ff81f2b30d80e
**config_digest:** 686a085b9a4504df58f4580b5a83f0c7b48b1580466739399d614116d20b2f94
**seed:** (no seed — real data)
**frozen_at:** 2026-07-13
**data_source:** yfinance

## Results

### Benchmarks (OOS)

| Metric | Candidate | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 1.27% | 60.27% | 0.00% | 1.17% |
| CAGR | 0.64% | 26.78% | 0.00% | 0.59% |
| Sharpe Ratio | 1.2950 | 1.8826 | N/A | 1.2902 |
| Max Drawdown | 0.47% | 10.11% | 0.00% | 0.39% |
| Win Rate | 37.5% | N/A | N/A | 50.0% |
| Total Trades | 32 | 0 | 0 | 24 |

### Extended Metrics
- Turnover (total): 75.7%
- Time in market: 71.9%
- Longest flat period: 30 bars
- Buy-and-hold exposure-adjusted return: 43.31%
- Buy-and-hold exposure-adjusted max drawdown: 7.27%

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000)
- Mean PnL: 2547.76
- Median PnL: 2525.63
- Std PnL: 1453.77
- 5th pctl: 193.08
- 95th pctl: 5120.46

### Parameter Sensitivity (OOS)
- lookback=20: return=1.27%, sharpe=1.2950, dd=0.47%, trades=32

### Walk-Forward
- Windows: 15
- Mean Sharpe: 0.6752

### Gate
- Min trades: 30
- Actual trades: 32
- Passed: YES
- Reason: Trade count 32 >= minimum 30

**notes:** Gate: PASSED. OOS trade count: 32. Policy: Path A. Candidate vs BH return: 1.27% vs 60.27%. Block bootstrap 5th pctl: 193.08.
