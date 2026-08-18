# US Equities Cross-Sectional Factor Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-only, dollar-neutral US Equities/ETFs cross-sectional factor research subsystem to evaluate 3 pre-registered factor anomalies (Momentum, Short-Term Reversal, and Low-Vol/Quality) net of realistic commissions, bid-ask spreads, and short borrowing costs.

**Architecture:** A multi-asset price matrix loader feeds a cross-sectional ranking engine. A market-neutral simulator constructs quantile weights, enforces zero net dollar exposure, computes rank IC, calculates borrow/commission friction, and evaluates the 5 frozen decision gates.

**Tech Stack:** Python 3.12+, pandas, numpy, scipy, pytest, existing TITAN research harness.

## Global Constraints

- Research-only. No live order placement, private broker credentials, or execution authority.
- Enforce strict dollar-neutrality ($\sum w_i = 0$) and point-in-time corporate action adjustments.
- Retain all negative results; do not alter OOS parameters or partitions after evaluation.

---

### Task 1: Multi-Asset Equities Universe Loader & Manifest

**Files:**
- Create: `research/equities/manifests/us_equities_etf_v1.json`, `src/titan/data/equities_universe.py`
- Test: `tests/data/test_equities_universe.py`

**Interfaces:**
- Produces: `EquitiesUniverseData` with aligned $T \times N$ price and return matrices, verified against manifest checksums.

- [ ] Write failing unit tests for data alignment, missing symbol handling, non-increasing dates, and manifest digest verification.
- [ ] Implement `EquitiesUniverseLoader` and `us_equities_etf_v1.json` manifest.
- [ ] Run `python -m pytest tests/data/test_equities_universe.py`; expect pass.

### Task 2: Cross-Sectional Factor Engine & Ranking

**Files:**
- Create: `src/titan/research/factors.py`
- Test: `tests/research/test_factors.py`

**Interfaces:**
- Produces: `compute_factor_scores(prices, factor_name, params) -> FactorScoreMatrix`.
- Implements:
  - `momentum_12_1m`: 252-day return skipping most recent 21 days.
  - `short_term_reversal_5d`: 5-day return deviation from cross-sectional mean.
  - `volatility_adjusted_momentum`: 63-day Sharpe or inverse-volatility ranked relative strength.

- [ ] Write failing tests verifying z-score normalization ($\mu=0, \sigma=1$), skip-window correctness, and ranking monotonicity.
- [ ] Implement `src/titan/research/factors.py`.
- [ ] Run `python -m pytest tests/research/test_factors.py`; expect pass.

### Task 3: Market-Neutral Simulator & Cost Attribution

**Files:**
- Create: `src/titan/backtest/factor_simulator.py`
- Test: `tests/backtest/test_factor_simulator.py`

**Interfaces:**
- Produces: `simulate_factor_portfolio(prices, factor_scores, cost_config) -> FactorSimulationResult`.
- Tracks: Long leg return, short leg return, short borrow fee (50 bps p.a.), commissions ($0.005/sh), spread (1 bps), turnover, and rank IC series.

- [ ] Write failing tests asserting dollar-neutrality ($\sum w_i = 0$), borrow fee accrual on short leg, and net attribution math.
- [ ] Implement `simulate_factor_portfolio` and `FactorCostModel`.
- [ ] Run `python -m pytest tests/backtest/test_factor_simulator.py`; expect pass.

### Task 4: Preregistration and Execution of EQ-001, EQ-002, EQ-003

**Files:**
- Create:
  - `research/equities/hypotheses/EQ-001-momentum.md` & `EQ-001-prereg.json`
  - `research/equities/hypotheses/EQ-002-reversal.md` & `EQ-002-prereg.json`
  - `research/equities/hypotheses/EQ-003-lowvol.md` & `EQ-003-prereg.json`
  - `src/titan/research/equities_factor_screen.py`
- Test: `tests/research/test_equities_factor_screen.py`

- [ ] Write failing tests validating preregistration schema, frozen partition enforcement, and gate evaluation logic.
- [ ] Implement `equities_factor_screen.py` and run evaluations for EQ-001, EQ-002, and EQ-003.
- [ ] Output evidence bundles: `research/equities/results/EQ-00X-evidence-bundle.json`.
- [ ] Run `python -m pytest tests/research/test_equities_factor_screen.py`; expect pass.

### Task 5: Factor Discovery Report & Boundary Validation

**Files:**
- Create: `research/equities/EQUITIES_FACTOR_REPORT.md`
- Test: `tests/research/test_equities_factor_screen.py`

- [ ] Write boundary test asserting the factor research package cannot import `TradeIntent` or `BrokerAdapter`.
- [ ] Compile scorecard and findings into `EQUITIES_FACTOR_REPORT.md`.
- [ ] Run complete test suite across the entire repository.
