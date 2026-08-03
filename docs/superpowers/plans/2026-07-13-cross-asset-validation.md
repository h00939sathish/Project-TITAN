# Cross-Asset Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make cross-asset replication reports distinguish absolute return from exposure-adjusted performance, prevent regression in textual trade-gate parsing, and preregister an unchanged volatility-regime study on a lower-correlated instrument without creating market data.

**Architecture:** Keep metric computation in `titan.research.metrics`, compose results in `ValidationHarness`, and render stored report values in `scripts/validate.py`. The preregistration is a research artifact only: it identifies the required data and keeps parameters fixed before any run.

**Tech Stack:** Python 3.12+, pytest, existing research harness and Markdown experiment registry.

## Global Constraints

- No strategy parameter, acceptance threshold, or Path A/Path B rule changes.
- No pooling of SPY/QQQ evidence in this change.
- No fixture is generated, downloaded, or altered; data provenance precedes execution.
- Existing frozen experiment records remain immutable.
- The gate parser must be covered by a test that fails before the implementation change.

---

### Task 1: Lock the trade-gate parser behavior

**Files:**
- Modify: `tests/research/test_harness.py`
- Modify: `src/titan/research/harness.py`

**Interfaces:**
- Consumes: `Hypothesis.success_criteria` containing `"Minimum 30 OOS trades"`.
- Produces: a failed validation report when the candidate has fewer than 30 trades, even if other criteria pass.

- [ ] Add a test with exactly 29 candidate trades and the `Minimum 30 OOS trades` criterion.
- [ ] Run `python -m pytest tests/research/test_harness.py -k minimum -v` and confirm the test fails because the parser does not recognise the wording.
- [ ] Implement the smallest parser change that extracts the required integer for both `Minimum N OOS trades` and `> N trades` wording.
- [ ] Re-run the focused test; it passes and reports the candidate as unsuccessful.

### Task 2: Add research-comparison metrics

**Files:**
- Modify: `tests/research/test_metrics.py`
- Modify: `src/titan/research/metrics.py`
- Modify: `src/titan/research/harness.py`
- Modify: `scripts/validate.py`

**Interfaces:**
- Consumes: candidate and buy-and-hold `BacktestResult` values plus OOS bar count and annualization factor.
- Produces: candidate CAGR, buy-and-hold CAGR, time-in-market fraction, and exposure-adjusted buy-and-hold return in `ValidationReport`.

- [ ] Add a deterministic metric test using a known equity curve and bar count; confirm it fails because CAGR is not reported.
- [ ] Add a deterministic comparison test where buy-and-hold return is scaled by the candidate’s declared exposure; confirm it fails because the report does not expose the value.
- [ ] Implement metric helpers with explicit zero/empty-input behavior and a 252-bar annualization default for daily fixtures.
- [ ] Render and persist both values in the validation report without changing any existing success criterion.
- [ ] Re-run focused metrics and harness tests; all pass.

### Task 3: Preregister the non-pooled cross-asset study

**Files:**
- Create: `knowledge/research/hypotheses/2026-07-13-volatility-regime-cross-asset.md`
- Modify: `knowledge/research/pooled-trade-count-policy.md`

**Interfaces:**
- Consumes: volatility-regime `v1.0.0`, unchanged parameters `{vol_window: 20, median_window: 60, vol_multiple: 1.0}`, Path A rules.
- Produces: a preregistered study on one declared lower-correlated ETF, separate instrument-level acceptance, and no pooled-trade claim.

- [ ] Select one broad, liquid, non-US-equity proxy only after its data entitlement and correlation measurement are recorded.
- [ ] Record the exact calendar, train/test split, unchanged parameters, data requirements, expected trade frequency, and all success/failure criteria.
- [ ] State that the study does not pool SPY, QQQ, and the new instrument for acceptance; it is an independent replication.
- [ ] Add the correlation and data-provenance prerequisites to the pooled-trade policy.

**Exit evidence:** the hypothesis remains preregistered until a separately versioned fixture passes data-quality checks.

### Task 4: Verify and document

**Files:**
- Modify: `README.md`

- [ ] Run focused research tests, then the complete Python suite.
- [ ] Run Ruff and mypy using project commands.
- [ ] Add the implementation-plan link to the README documentation index.

**Exit evidence:** tests and static checks pass; the change has no new experiment result and no change to frozen evidence.

