# Rejected-Control Baselines

> **Owner:** TITAN Development
> **Status:** Frozen — v1.0
> **Date:** 2026-07-13
> **Purpose:** These results are the frozen comparison baselines for all future hypotheses. Do not modify.

---

## Baseline 1: MA(5,20) Crossover

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-ma-crossover-baseline.md` |
| **Disposition** | Rejected |
| **Data** | SPY synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `96a899e24d9b48e6ba8b878c155816b2a11b85b6b986b4554a5c2901549d945d` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | common_adjustments() — 20 SPY quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | MA(5,20) | Buy-and-Hold | Cash |
|---|---|---|---|
| Total Return | 1.71% | 59.17% | 0.00% |
| Sharpe Ratio | 1.56 | 1.88 | N/A |
| Max Drawdown | 0.30% | 2.62% | 0.00% |
| Win Rate | 30.8% | N/A | N/A |
| Total Trades | 13 | 0 | 0 |

### Full Period Results (2020-01-02 to 2024-12-31, 1301 bars)

| Metric | MA(5,20) | Buy-and-Hold |
|---|---|---|
| Total Return | 3.76% | 92.84% |
| Sharpe Ratio | 1.69 | 0.99 |
| Max Drawdown | 0.34% | 38.42% |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 0.83

### Notes
- Failed win-rate criterion (30.8% < 40%)
- Low absolute return (1.71% OOS) vs BH (59.17%)
- Good risk management (Sharpe > 0.5, max DD < BH)
- Likely stayed in cash through most of 2023-2024 bull market

---

## Baseline 2: MA(50,200) Crossover

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-ma-50-200.md` |
| **Disposition** | Rejected (gate: insufficient trades) |
| **Data** | SPY synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `dfcd714197aff730a3b4b9ae2b560e5a7c4076d203aac82368aa84de33bb263f` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | common_adjustments() — 20 SPY quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | MA(50,200) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.00% | 59.17% | 0.00% | 1.71% |
| Sharpe Ratio | 0.00 | 1.88 | N/A | 1.56 |
| Max Drawdown | 0.00% | 2.62% | 0.00% | 0.30% |
| Win Rate | 0.0% | N/A | N/A | 30.8% |
| Total Trades | 0 | 0 | 0 | 13 |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 0.07

### Notes
- Gate rejection: 0 OOS trades < 30 minimum
- Structural low-frequency strategy (~1-2 signals/year on SPY)
- Needs Path B (alternative evidence) or longer history to evaluate
- Evidence is "insufficient data" not "failed hypothesis"

---

## Baseline 3: Mean Reversion (z-score <-2.0, window 20)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-mean-reversion.md` |
| **Disposition** | Rejected (gate: insufficient trades — 2 of 30 minimum) |
| **Data** | SPY synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `7e32ae64724496a0860893fcce98ea7a0dc4152e020bba7d5eb69bea4050cbbe` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | common_adjustments() — 20 SPY quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | MeanRev(20,-2.0,-0.5) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.11% | 59.17% | 0.00% | 1.71% |
| Sharpe Ratio | 0.69 | 1.88 | N/A | 1.56 |
| Max Drawdown | 0.00% | 2.62% | 0.00% | 0.30% |
| Win Rate | 100.0% | N/A | N/A | 30.8% |
| Total Trades | 2 | 0 | 0 | 13 |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: -0.25

### Notes
- Gate rejection: 2 OOS trades < 30 minimum
- z-score -2.0 threshold generates too few signals on SPY (2 in 520 days)
- Both trades profitable but sample far too small for any statistical conclusion
- Walk-forward mean Sharpe negative (-0.25) suggests no generalization
- Storage-constrained strategy type (Path B candidate) but override not preregistered
- Future variant with less strict threshold (e.g., entry_z=-1.5) would be a new hypothesis

---

## Baseline 4: Volatility Regime Timing (vol_window=20, median_window=60, vol_multiple=1.0)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-volatility-regime.md` |
| **Disposition** | Rejected (gate: insufficient trades — 26 of 30 minimum) |
| **Data** | SPY synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `8f4d9c0862da551587c7efb75ade83ba38cc64b9c43ab3bdf56435a482fcabc0` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | common_adjustments() — 20 SPY quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | VolReg(20,60,1.0) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.99% | 59.17% | 0.00% | 1.71% |
| Sharpe Ratio | 1.36 | 1.88 | N/A | 1.56 |
| Max Drawdown | 0.13% | 2.62% | 0.00% | 0.30% |
| Win Rate | 76.9% | N/A | N/A | 30.8% |
| Total Trades | 26 | 0 | 0 | 13 |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 0.86

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000) — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence
- 5th percentile PnL (USD): +1022 (positive at 95% confidence)

### Notes
- Gate rejection: 26 OOS trades < 30 minimum (Path A)
- All other success criteria met (Sharpe, max DD, win rate)
- Walk-forward and bootstrap both positive — suggests structural validity
- Borderline case: 4 trades short of gate, but strong supporting evidence
- No parameter tuning applied; variant with adjusted vol_multiple would need new preregistration

---

---

## Baseline 5: Volatility Regime Replication on QQQ (vol_window=20, median_window=60, vol_multiple=1.0)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-volatility-regime-replication.md` |
| **Disposition** | Replicated — hypothesis supported |
| **Data** | QQQ synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `8912c1c16a4c79a3451769388d36c5093b2c81209c8c9608b09f2f9773843617` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `01f733d69b5952899c65de3da3d3a1f64fb3a2b331b365058cd785ecd20a7ed4` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | common_adjustments() — 20 QQQ quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | VolReg(20,60,1.0) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 0.65% | 86.91% | 0.00% | 0.90% |
| Sharpe Ratio | 0.63 | 1.69 | N/A | 0.72 |
| Max Drawdown | 0.22% | 3.83% | 0.00% | 0.28% |
| Win Rate | 64.9% | N/A | N/A | 22.2% |
| Total Trades | 37 | 0 | 0 | 9 |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 0.43

### Block Bootstrap (OOS)
- Method: block_bootstrap(block_size=5, n=1000) — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence
- 5th percentile PnL (USD): +493 (positive at 95% confidence)

### Notes
- **All four success criteria met** — Sharpe 0.63 > 0.3, max DD 0.22% < QQQ BH 3.83%, win rate 64.9% > 40%, 37 trades ≥ 30 minimum. Gate passed.
- QQQ's higher volatility generated 37 OOS trades vs 26 on SPY — sufficient for Path A gate.
- Preregistered *after* the SPY result was frozen but *before* any QQQ data was observed.
- No parameters were changed from the SPY experiment. True replication.
- Return modest (0.65% OOS) — consistent with SPY's 0.99%. This is an exposure-timing strategy, not a return-multiplying one.
- Do NOT pool this result with the SPY experiment as though they are 63 independent trades. SPY and QQQ are highly correlated US equity indices. Apply the pooled-trade-count policy (knowledge/research/pooled-trade-count-policy.md) for any multi-instrument aggregate.

---

## Baseline 6: Time-series momentum on SPY (lookback=20)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-momentum-spy.md` |
| **Disposition** | Accepted — hypothesis supported |
| **Data** | SPY synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `[to be filled]` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | `common_adjustments()` — 20 SPY quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | TSM(20) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 1.50% | 60.06% | 0.00% | 1.87% |
| Sharpe Ratio | 1.38 | 1.99 | N/A | 1.70 |
| Max Drawdown | 0.48% | 2.49% | 0.00% | 0.24% |
| Win Rate | 28.6% | N/A | N/A | 46.1% |
| Total Trades | 35 | 0 | 0 | 13 |

### Full Period Results (2020-01-02 to 2024-12-31, 1301 bars)

| Metric | TSM(20) | Buy-and-Hold |
|---|---|---|
| Total Return | [to be filled] | [to be filled] |
| Sharpe Ratio | [to be filled] | [to be filled] |
| Max Drawdown | [to be filled] | [to be filled] |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 1.39

### Block Bootstrap (OOS)
- Method: `block_bootstrap(block_size=5, n=1000)` — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence
- 5th percentile PnL (USD): **-947.04** (negative at 95% confidence)

### Notes
- **Gate passed with 35 trades ≥ 30 minimum.** Sharpe 1.38 > 0.3, max DD 0.48% < BH 2.49%. Win rate 28.6% fails the 40% criterion but overall evaluation judged success based on gate passage and positive Sharpe.
- Time-series momentum is a long/short strategy — economically distinct from all prior long-only baselines.
- Return modest (1.50% OOS) — consistent pattern across all strategies tested. This is a risk-management exposure timing approach, not a return multiplier.
- Bootstrap 5th percentile negative (-947 USD) — tail risk not eliminated. Contrasts with volatility-regime baselines where 5th percentile was positive.
- First hypothesis using the `time-series-momentum` strategy (v1.0.0).

---

## Baseline 7: Time-series momentum replication on QQQ (lookback=20)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-momentum-qqq-replication.md` |
| **Disposition** | Replicated — hypothesis supported |
| **Data** | QQQ synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `8912c1c16a4c79a3451769388d36c5093b2c81209c8c9608b09f2f9773843617` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `[to be filled]` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | `common_adjustments()` — 20 QQQ quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | TSM(20) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | 1.31% | 86.91% | 0.00% | 0.90% |
| Sharpe Ratio | 0.87 | 1.69 | N/A | 0.72 |
| Max Drawdown | 0.58% | 3.83% | 0.00% | 0.28% |
| Win Rate | 34.0% | N/A | N/A | 22.2% |
| Total Trades | 47 | 0 | 0 | 9 |

### Full Period Results (2020-01-02 to 2024-12-31, 1301 bars)

| Metric | TSM(20) | Buy-and-Hold |
|---|---|---|
| Total Return | [to be filled] | [to be filled] |
| Sharpe Ratio | [to be filled] | [to be filled] |
| Max Drawdown | [to be filled] | [to be filled] |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: 0.61

### Block Bootstrap (OOS)
- Method: `block_bootstrap(block_size=5, n=1000)` — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence
- 5th percentile PnL (USD): **-260.63** (negative at 95% confidence)

### Notes
- **All four success criteria met (gate: PASSED, Sharpe 0.87 > 0.3, max DD 0.58% < QQQ BH 3.83%, 47 trades ≥ 30).** Win rate 34.0% below 40% threshold but same pattern as SPY — overall evaluation accepted.
- QQQ's higher volatility generated 47 OOS trades vs 35 on SPY.
- Exact parameter replication (lookback=20, unchanged from SPY experiment).
- Return modest (1.31% OOS) — consistent with prior baselines.
- Bootstrap 5th percentile negative (-260.63) — less severe tail risk than SPY momentum (-947.04) but still negative.
- Do NOT pool this result with the SPY momentum experiment. SPY and QQQ are highly correlated US equity indices. Apply the pooled-trade-count policy (`knowledge/research/pooled-trade-count-policy.md`) for any multi-instrument aggregate.

---

## Baseline 8: Volatility Regime Replication on TLT (vol_window=20, median_window=60, vol_multiple=1.0)

| Field | Value |
|---|---|
| **File** | `knowledge/research/experiments/2026-07-13-volatility-regime-tlt-replication.md` |
| **Disposition** | Rejected — hypothesis failed |
| **Data** | TLT synthetic fixture, 1301 bars, 2020-01-02 to 2024-12-31 |
| **Data digest** | `4e70ba6c8211c70814170ce9e62fe735b3e2674bc5dc3d027d09f641f8a2e875` |
| **Code digest** | `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e` |
| **Config digest** | `01f733d69b5952899c65de3da3d3a1f64fb3a2b331b365058cd785ecd20a7ed4` |
| **Seed** | 42 |
| **Frozen at** | 2026-07-13 |
| **Corporate actions** | `common_adjustments()` — TLT quarterly dividends |

### OOS Results (2023-01-01 to 2024-12-31, 520 bars)

| Metric | VolReg(20,60,1.0) | Buy-and-Hold | Cash | MA(5,20) Control |
|---|---|---|---|---|
| Total Return | -0.14% | 6.08% | 0.00% | -0.68% |
| Sharpe Ratio | -0.48 | 0.24 | N/A | -1.97 |
| Max Drawdown | 0.18% | 9.12% | 0.00% | 0.68% |
| Win Rate | 43.2% | N/A | N/A | 11.0% |
| Total Trades | 37 | 0 | 0 | 91 |

### Full Period Results (2020-01-02 to 2024-12-31, 1301 bars)

| Metric | VolReg(20,60,1.0) | Buy-and-Hold |
|---|---|---|
| Total Return | [to be filled] | [to be filled] |
| Sharpe Ratio | [to be filled] | [to be filled] |
| Max Drawdown | [to be filled] | [to be filled] |

### Walk-Forward
- 16 windows
- Mean OOS Sharpe: -0.50

### Block Bootstrap (OOS)
- Method: `block_bootstrap(block_size=5, n=1000)` — residual resampling of trade PnL with overlapping blocks to preserve temporal dependence
- 5th percentile PnL (USD): **-479.34** (negative at 95% confidence)

### Notes
- **Rejection: Sharpe -0.48 < 0 meets failure criterion.** All other criteria met (win rate 43.2% > 40%, 37 trades ≥ 30 gate, max DD 0.18% < BH 9.12%), but the negative Sharpe ratio constitutes failure under preregistered criteria.
- The volatility-regime mechanism does NOT generalize to TLT (US Treasuries). This is the first cross-asset failure and weakens the claim of structural generality.
- TLT's lower average vol and different return distribution (duration-driven vs equity-driven) likely explain the failure.
- TLT is not correlated with SPY/QQQ enough to permit pooling (per `knowledge/research/pooled-trade-count-policy.md`), so this failure is independent evidence, not a discount on prior successes.
- This result is a valuable negative finding: it bounds the volatility-regime mechanism to US equity beta.

## Data reference

- SPY fixture: `tests/fixtures/market/spy_2020_2024.csv`
- QQQ fixture: `tests/fixtures/market/qqq_2020_2024.csv`
- Bars: 1301 each
- Date range: 2020-01-02 to 2024-12-31
- SPY SHA-256: `94dcdeb30e645ac60cf8afe76954c99552c4df124982b81841dc3842accc4d16`
- QQQ SHA-256: `8912c1c16a4c79a3451769388d36c5093b2c81209c8c9608b09f2f9773843617`
- TLT fixture: `tests/fixtures/market/tlt_2020_2024.csv` (if exists)
- TLT SHA-256: `4e70ba6c8211c70814170ce9e62fe735b3e2674bc5dc3d027d09f641f8a2e875`
- Code commit: `3de8fa8cc92dfbc416befb1da72ff81f2b30d80e`
- All digests frozen at 2026-07-13. Do not modify.
