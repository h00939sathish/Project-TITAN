# Sample Adequacy Policy

> **Owner:** TITAN Development
> **Status:** Active — v1.0
> **Date:** 2026-07-13

## Purpose

Ensure that a hypothesis is tested on enough out-of-sample data to produce statistically meaningful results. A strategy can appear to succeed or fail purely due to insufficient data — not because the economic rationale is valid or invalid.

## Core rule

**A hypothesis must generate at least 30 OOS trades** before its success/failure criteria are evaluated, **unless** a documented alternative evidence standard is provided.

## Rationale for 30 trades

- A minimum of ~30 independent observations is a conventional threshold for central-limit-theorem approximations to hold.
- Below 30 trades, a strategy's Sharpe, win rate, and drawdown are dominated by idiosyncratic timing luck.
- The 30-trade rule applies to the **OOS (test) period only**. Trades during the training/warmup period do not count.

## Two paths to acceptance

### Path A: Standard (30+ OOS trades)

Meet the standard gate. Use block bootstrap to estimate confidence intervals. Compare Sharpe, max DD, and return against all three benchmarks. Hypothesis must pass all success criteria.

### Path B: Low-frequency strategy (alternative evidence)

A strategy that **structurally cannot** produce 30 OOS trades within the available data window may still be evaluated if it provides all of:

1. **Structural rationale document:** Explain why low turnover is inherent to the strategy's design (e.g., "200-day MA crossover by construction produces at most 1-2 signals per year"). This must be written and frozen **before** the OOS results are computed.

2. **Longer history extension:** If available, extend the OOS window to cover more market regimes. Document the expanded window and justify why it remains fair (e.g., "extended to 2015-2024 to capture 4+ market regimes").

3. **Alternative evidence standard:** One of:
   - **Per-signal analysis:** Evaluate each individual trade against a random-entry null distribution (Monte Carlo of random entry/exit at same frequency).
   - **Multi-instrument:** Run the same low-frequency signal across N uncorrelated instruments; treat each instrument as an independent observation.
   - **Return on invested capital (ROIC):** Report return during in-market periods only, with the rationale that the strategy is an "opportunistic allocation" that should be compared against a benchmark scaled by time-in-market.
   - **Rejection-and-accept:** The hypothesis is rejected under the standard gate but marked as "insufficient data" rather than "failed hypothesis." A longer test window is required before final disposition.

4. **Pre-registered override:** The alternative evidence path must be specified at hypothesis preregistration time, not after seeing OOS results.

## Examples

| Strategy | Structural turnover | Path | Evidence |
|---|---|---|---|
| MA(5,20) on SPY daily | ~10-20 trades/year | A (standard) | 30 trades in 2 years is achievable |
| MA(50,200) on SPY daily | ~1-2 trades/year | B (low-freq) | Needs longer history or multi-instrument |
| Buy-write monthly | ~12 trades/year | B (low-freq) | Needs 3+ years or per-signal analysis |
| Earnings gap strategy | ~4 trades/quarter | A (standard) | 30 trades in 2 years is achievable |

## Data window policy

- **Minimum OOS window:** 2 years (504 trading days) for standard Path A.
- **Recommended OOS window:** 5+ years across multiple regimes (bull, bear, crash, recovery).
- A hypothesis tested on a single market regime (e.g., only bull market) is **automatically inconclusive** regardless of trade count.
- The test window must be declared at preregistration. Extending the test window after seeing results is not permitted.

## Review

This policy is reviewed quarterly and whenever a low-frequency hypothesis is evaluated under Path B for the first time.
