# EQ-002 — Core-7 12-1M Cross-Sectional Reversal Counter-Test

- **Status:** Preregistered (2026-08-17). Active under ADR-030.
- **Economic Mechanism:** In a concentrated universe of broad ETFs and mega-caps, historical 12-month relative underperformers experience powerful cyclical mean-reversion and catch-up rotations during subsequent macro expansions, systematically outperforming previous momentum winners.
- **Experimental Design:** Direct causal counter-test of `EQ-001`. Changes only one variable: inverting the ranking ($Momentum \rightarrow Reversal$) while preserving the identical Core-7 universe, identical historical partitions, identical 21-day rebalancing, and identical cost model.

## Frozen Specification

- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT`
- **Signal:** 12-1 Month Cross-Sectional Reversal ($S_{i,t} = -(\frac{P_{i,t-21}}{P_{i,t-252}} - 1)$, Cross-Sectional Z-Score).
- **Portfolio Construction:**
  - Long Bottom 2 (worst historical performers, $+50\%$ gross each).
  - Short Top 2 (best historical performers, $-50\%$ gross each).
  - Middle 3 Neutral ($0\%$).
  - Dollar-neutral: $\sum w_i = 0$.
- **Rebalance Frequency:** 21 trading days (monthly).
- **Partitions:**
  - In-Sample (IS): 2020-01-02 to 2022-12-31 (36 months).
  - Out-of-Sample (OOS): 2023-01-03 to 2024-12-31 (24 months, frozen).
- **Cost Model:**
  - Commissions: $\$0.005$ per share.
  - Bid-Ask Spread: $1.0$ bps.
  - Slippage Impact: $0.5$ bps.
  - Short Borrow: $50$ bps annual rate accrued daily.

## Decision Gates & Scientific Criteria

1. **Rank IC:** Mean OOS Spearman Rank IC $> 0.0$.
2. **Monotonicity:** $\text{Long Top 2 (Laggards)} > \text{Middle 3} > \text{Short Bottom 2 (Leaders)}$.
3. **Net Performance:** OOS Net Sharpe $> 0.0$ and positive net return after all friction.
4. **Zero Parameter Mining:** If 12-1M Reversal fails to clear OOS gates, record the failure and formulate `EQ-003` without lookback sweeping.
