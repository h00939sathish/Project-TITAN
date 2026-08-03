# Phase I — Research Validity Program

> **Goal:** Establish whether a narrow, explainable strategy hypothesis survives unbiased validation.
> **Exit gate:** One strategy package has a reproducible, economically explained, out-of-sample result that survives its predeclared stress tests.

## Tasks

| Task | Description | Type | Dependencies |
|---|---|---|---|
| **I1** | Experiment registry — schema + first entry | Doc | None |
| **I2** | Point-in-time data quality tests | Code | None |
| **I3** | Baseline strategy + benchmark selection | Doc | None |
| **I4** | Walk-forward validation pipeline | Code | I2, I3 |
| **I5** | Enhanced performance metrics (volatility, hit rate, tail loss, exposure, capacity proxy) | Code | None (extends results.py) |
| **I6** | Reproduce + adversarial review | Doc + Test | I4, I5 |

## Constraints

- No changes to Rust core
- No credentials in code, docs, or test fixtures
- All experimental results preserved in knowledge/research/
- Negative results (hypothesis rejected) are retained — not deleted

---

### I1: Experiment registry

**Create:** `knowledge/research/registry.md` — schema and template
**Create:** `knowledge/research/experiments/2026-07-13-ma-crossover-baseline.md` — first entry

The registry schema defines one experiment record:
- **id:** unique identifier
- **hypothesis:** one-sentence economic rationale
- **owner:** developer name
- **data_digest:** SHA-256 of input data
- **code_digest:** SHA-256 of strategy/backtest code
- **config_digest:** SHA-256 of `json.dumps({"strategy_id": sid, "params": params}, sort_keys=True)`
- **calendar:** date range, exchange calendar used
- **universe:** instruments included
- **success_criteria:** predeclared — what must be true to consider this hypothesis supported
- **failure_criteria:** predeclared — what would refute the hypothesis
- **costs:** fee/slippage/commission assumptions
- **results:** BacktestResult metrics
- **reviewer:** who reviewed/verified
- **disposition:** Accepted / Rejected / Inconclusive
- **notes:** qualitative observations

The first entry records the MovingAverageCrossover baseline run.

### I2: Point-in-time data tests

**Create:** `tests/data/test_point_in_time.py`

Tests that verify the data pipeline prevents common biases:

1. **Survivorship bias detection:** Load a fixture containing a delisted symbol; verify the data quality check flags it (or documents that it can't detect it).
2. **Look-ahead leakage test:** Given a sorted CSV with future data, verify that a sequential reader sees only past data at each step.
3. **Missing session detection:** Load fixtures with gaps in trading calendar; verify gaps are flagged.
4. **Stale data detection:** Verify that data older than a threshold is flagged by a staleness check function.
5. **Corporate action handling:** Test that split/dividend adjustments are detected (current: none implemented — document the gap).
6. **Vendor correction detection:** Test that data with differing source checksums is flagged.

For tests that can't pass (no implementation yet), write them as skipped/xfail with a reference to the gap.

Write test fixtures as inline data in the tests.

### I3: Baseline strategy + benchmark

**Create:** `knowledge/research/baseline-strategy.md`

Document:
- **Strategy:** MovingAverageCrossover(5, 20) on daily bars
- **Economic rationale:** Trend following captures momentum — short-term MA crossing above long-term MA indicates upward price pressure, and vice versa. This is not novel; it is the simplest testable hypothesis.
- **Instrument:** SPY (S&P 500 ETF) — most liquid, simplest corporate actions, longest history
- **Benchmark:** Buy-and-hold SPY over the same period
- **Data source:** CSV fixture (sample_ohlcv.csv or Polygon.io sample)
- **Period:** Recommend 2020-01-01 to 2024-12-31 (5 years, covers COVID crash, recovery, 2022 bear market, 2023 recovery)
- **Train/validation/test split:** 2020-2021 train, 2022 validation, 2023-2024 test
- **Success criteria:** Sharpe > 0.5 out-of-sample, max drawdown < benchmark max drawdown, win rate > 40%
- **Failure criteria:** Sharpe < 0 out-of-sample, or strategy loses to benchmark on risk-adjusted basis

### I4: Walk-forward validation pipeline

**Create:** `scripts/validate.py` — script that runs the full validation workflow
**Create:** `knowledge/research/experiments/2026-07-13-ma-crossover-baseline.md` — update with actual results

The script should:
1. Load daily OHLCV data (CSV fixture or inline data)
2. Run MovingAverageCrossover(5, 20) over the data
3. Use BarConservativeFillModel for fills
4. Track equity curve and trades
5. Walk-forward: retrain (recalc MAs) every N bars, validate on next M bars
6. Parameter perturbation: test ±1 period on both fast and slow MAs
7. Monte Carlo: resample trade sequence 1000 times, report distribution of returns
8. Fee/slippage stress: test at 0.5x, 1x, 2x, 5x baseline slippage
9. Output BacktestResult for each scenario

### I5: Enhanced performance metrics

**Modify:** `src/titan/backtest/results.py`

Add to `BacktestResult`:
- `volatility_annual_pct: float` — annualized volatility of daily returns
- `hit_rate_pct: float` — fraction of winning trades (alias)
- `tail_loss_pct: float` — 5th percentile worst daily return
- `avg_exposure_pct: float` — average fraction of capital deployed
- `capacity_proxy: float` — average position size as fraction of ADV (approximate)
- `calmar_ratio: float` — annualized return / max drawdown
- `profit_factor: float` — gross profit / gross loss

Update `compute()` to populate these fields.

### I6: Reproduction + adversarial review

**Create:** `tests/research/test_independent_reproduction.py`
**Create:** `knowledge/research/reproduction-check.md`

Reproduction test:
1. Run the same strategy code on the same data, verify byte-identical BacktestResult
2. Run with the same code but shuffled data order — verify results differ (sanity check)
3. Run the adversarial review checklist: does the hypothesis survive attempts to invalidate it?

Adversarial review questions (documented in reproduction-check.md):
1. Is the strategy just overfitting to the train period? (Check: out-of-sample performance vs in-sample)
2. Does it work on other instruments? (Check: run on QQQ, IWM)
3. Does parameter sensitivity kill it? (Check: perturbation grid)
4. Would it survive trading costs at scale? (Check: capacity proxy)
5. Is there a simpler explanation? (Buy-and-hold comparison)
6. Is the data clean? (Check: point-in-time tests)
7. Are results driven by a few outlier days? (Check: tail loss, distribution of returns)

## Phase exit gate check

- [ ] Registry exists with at least one complete experiment entry
- [ ] Point-in-time data tests document known biases (passing or documented as gaps)
- [ ] Baseline strategy and benchmark are selected and documented
- [ ] Walk-forward validation script runs without error
- [ ] Enhanced performance metrics are calculated
- [ ] Reproduction tests pass the coincidence check (identical inputs → identical outputs)
- [ ] Adversarial review questions are answered in the experiment record
- [ ] Negative results (if any) are retained

---

**File list by task:**

I1: `knowledge/research/registry.md`, `knowledge/research/experiments/2026-07-13-ma-crossover-baseline.md`
I2: `tests/data/test_point_in_time.py`
I3: `knowledge/research/baseline-strategy.md`
I4: `scripts/validate.py`
I5: `src/titan/backtest/results.py` (modify)
I6: `tests/research/test_independent_reproduction.py`, `knowledge/research/reproduction-check.md`
