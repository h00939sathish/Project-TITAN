# EQ-004 — Broad-50 US Equities 12-1M Cross-Sectional Reversal Evaluation

- **Status:** Pending Governance Ratification (ADR-030 & EquitiesFactorResearch.spec.md). Sealed before acquisition.
- **Economic Mechanism:** Evaluates whether the 12-1M cross-sectional reversal discovered in `EQ-002` generalizes across a broad cross-section of liquid individual US equities ($N=50$), or if it was an artifact of the concentrated 7-asset ETF basket.
- **Experimental Design:** Tests dollar-neutral 12-1M reversal ranking on the Top 50 liquid S&P 500 equities sourced point-in-time as of 2020-01-02.

## Frozen Specification

- **Universe ($N=50$):** Top 50 liquid US equities by market cap and 90-day ADV within the S&P 500 as of 2020-01-02.
  - Sourced strictly point-in-time (delistings, mergers, and corporate actions preserved).
  - ETB status verified as of inception.
- **Signal Formulation:**
  $$S_{i,t} = - \left( \frac{P_{i,t-21}}{P_{i,t-252}} - 1 \right), \quad z_{i,t} = \frac{S_{i,t} - \mu_t}{\sigma_t}$$
- **Portfolio Construction:**
  - Long Decile 1 & 2 (Bottom 10 historical performers / Laggards, $+10\%$ gross each $\implies +100\%$ gross).
  - Short Decile 9 & 10 (Top 10 historical performers / Leaders, $-10\%$ gross each $\implies -100\%$ gross).
  - Middle Deciles 3–8 Neutral ($0\%$).
  - **Gross Exposure:** $200\%$ ($+100\%$ long, $-100\%$ short, $0\%$ net dollar exposure).
- **Rebalance Frequency:** 21 trading days (monthly).
- **Partitions:**
  - In-Sample (IS): 2020-01-02 to 2022-12-31 (36 months).
  - Out-of-Sample (OOS): 2023-01-03 to 2024-12-31 (24 months, sealed).
- **Cost Model:**
  - Commissions: $\$0.005$ per share (IBKR Pro).
  - Bid-Ask Spread: $1.0$ bps.
  - Execution Slippage Impact: $0.5$ bps.
  - Short Borrow: $50$ bps annual rate accrued daily.

## Decision Gates & Acceptance Criteria

1. **Rank IC:** Mean OOS Spearman Rank IC $> 0.0$ (positive in $\ge 50\%$ of monthly rebalance windows).
2. **10-Decile Monotonicity:** Strict ordering across all 10 deciles ($D_1 > D_2 > \dots > D_{10}$).
3. **Net Performance:** OOS Net Sharpe $> 0.0$ after all commissions, spread, slippage impact, and short borrow fees.
4. **Drawdown Limit:** OOS Maximum Drawdown $\le 25.0\%$.
5. **Zero Parameter Mining:** If `EQ-004` fails to meet acceptance gates, record an absorbing `negative_result` without post-hoc lookback adjustments.
