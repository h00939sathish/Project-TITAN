# US Equities Cross-Sectional Factor Discovery Charter

- **Status:** Proposed — research-only; governed by ADR-030
- **Scope:** US Equities and Liquid US Sector/Asset ETFs; market-neutral cross-sectional ranking; no live capital authority

## Objective

Determine whether a dollar-neutral, market-beta-hedged cross-sectional factor model generates reproducible, statistically significant alpha net of commissions, bid-ask spreads, and short borrowing costs on liquid US instruments.

## Universe & Data Contract

1. **Universe:** Liquid US Equities & Sector ETFs (SPY, QQQ, IWM, XLF, XLK, XLE, XLV, XLI, XLU, XLP, XLY, XLB, TLT).
2. **Data Integrity:** Point-in-time adjusted closes accounting for stock splits, dividends, and corporate distributions (`src/titan/backtest/corporate_actions.py`).
3. **Calendar:** Strict NYSE/NASDAQ regular trading hours (09:30 - 16:00 ET) and market holiday enforcement (`src/titan/data/calendar.py`).
4. **Minimum Admissible Data:** Contiguous 48+ months of daily bar data (2020-01 to 2024-12+), partitioned into:
   - In-Sample (IS): 2020-01-01 to 2022-12-31 (36 months).
   - Out-of-Sample (OOS): 2023-01-01 to 2024-12-31 (24 months).

## Candidate Hypotheses

1. **`EQ-001` (Cross-Sectional 12-1M Momentum):**
   - Ranks the universe by cumulative return over the past 252 trading days, skipping the most recent 21 trading days (1 month) to eliminate short-term microstructure reversal.
   - Long top $K$ instruments, short bottom $K$ instruments with equal dollar weighting.
2. **`EQ-002` (Cross-Sectional Short-Term Reversal):**
   - Ranks the universe by 5-day return deviation from the cross-sectional mean.
   - Long oversold laggards, short overextended leaders to capture liquidity provision / mean-reversion premia.
3. **`EQ-003` (Cross-Sectional Volatility-Adjusted Momentum / Low-Vol):**
   - Ranks the universe by 63-day Sharpe ratio or inverse historical realized volatility.
   - Long high-risk-adjusted quality assets, short high-volatility speculative laggards.

## Mandatory Cost & Financing Model

Every factor evaluation must compute gross selection return and explicitly attribute:
- **Broker Commissions:** $0.005 per share (IBKR standard tier) or declared fixed bps.
- **Execution Spread:** 1.0 bps per turnover turn (top-tier ETF liquidity).
- **Short Borrowing Fee:** 50 bps annual rate on short leg market value, accrued daily.
- **Cash Financing / Cash Drag:** Realistic risk-free rate on cash collateral.

## Frozen Decision Gates

- **Gate 1 (OOS Net Sharpe):** Annualized Net Sharpe ratio $\ge 1.0$ on OOS partition.
- **Gate 2 (Rank IC Consistency):** Cross-sectional Spearman rank correlation between factor scores and forward 21-day returns positive in $\ge 70\%$ of rolling windows (mean IC $\ge 0.05$).
- **Gate 3 (Monotonic Quantile Spread):** Top quantile return strictly exceeds median quantile, and median quantile strictly exceeds bottom quantile.
- **Gate 4 (Turnover & Capacity):** Monthly portfolio turnover $\le 60\%$ (preserving net return after trading friction).
- **Gate 5 (Drawdown Bound):** Maximum peak-to-trough drawdown $\le 15.0\%$ during OOS period.

## Terminal Rule

If an evaluated hypothesis fails any gate on OOS data, record an absorbing `negative_result` in `research/equities/results/`. Parameter snooping or re-running on OOS after failure is strictly prohibited by the TITAN Agent Constitution.
