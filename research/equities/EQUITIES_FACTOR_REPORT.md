# US Equities Cross-Sectional Factor Discovery Report

- **Date:** 2026-08-16
- **Governing ADR:** ADR-030 (Proposed & Evaluated under Architecture Council / Risk Owner review)
- **Asset Scope:** US Equities & Sector ETFs (SPY, QQQ, IWM, XLF, XLK, XLE, XLV, XLI, XLU, XLP, XLY, XLB, TLT)
- **Methodology:** Point-in-time cross-sectional factor ranking; market-neutral (dollar-neutral long top $K$, short bottom $K$) construction; explicit friction modeling (IBKR commissions, 1 bps spread, 50 bps annual short borrow fee).

---

## Executive Summary Scorecard

| Hypothesis | Factor Family | IS Net Sharpe | OOS Net Sharpe | OOS Max DD | OOS Monthly Turnover | OOS Mean Rank IC | Final Verdict |
|---|---|---|---|---|---|---|---|
| **EQ-001** | 12-1M Momentum | 0.48 | **0.70** | **8.30%** | **16.79%** | -0.017 | ❌ `negative_result` (Gate 1 & 2 failed) |
| **EQ-002** | 5-Day Reversal | 0.03 | **-0.17** | **17.93%** | **414.49%** | -0.034 | ❌ `negative_result` (All gates failed) |
| **EQ-003** | Vol-Adjusted Momentum | 0.62 | **0.47** | **10.29%** | **22.17%** | -0.037 | ❌ `negative_result` (Gate 1 & 2 failed) |

---

## Detailed Analytical Findings

### 1. EQ-001 (12-1M Cross-Sectional Momentum)
- **Mechanism:** Exploits medium-term drift and institutional sector allocation momentum, skipping the most recent 1-month window to eliminate short-term reversal noise.
- **Results:**
  - In-Sample (2020–2022): Generated positive net return (+4.16% ann., Sharpe 0.48) with high rank IC consistency (76% positive months, mean IC +0.158).
  - Out-of-Sample (2023–2024): Remained net positive (+6.47% ann., Sharpe 0.70) with low drawdown (8.30%) and modest monthly turnover (16.79%).
  - **Failure Reason:** OOS Net Sharpe of 0.70 missed the frozen $\ge 1.0$ gate requirement, and forward Rank IC deteriorated during rapid 2023 tech/mega-cap concentration shifts (Magnificent 7 divergence).

### 2. EQ-002 (5-Day Short-Term Reversal)
- **Mechanism:** Attempts to capture liquidity provision premia by buying weekly oversold ETF laggards and shorting overbought leaders.
- **Results:**
  - In-Sample & Out-of-Sample: Severe breakdown under realistic execution costs.
  - **Failure Reason:** Extreme monthly turnover (~414%/month) generates substantial commission, spread, and short-borrow drag (-2.64% per year in total friction), wiping out the small gross reversal spread.

### 3. EQ-003 (Volatility-Adjusted Momentum / Low-Vol)
- **Mechanism:** Penalizes volatile sector spikes and rewards consistent risk-adjusted trends by scaling momentum scores by rolling 63-day realized volatility.
- **Results:**
  - In-Sample (2020–2022): Strongest IS performance (+5.36% ann., Sharpe 0.62, Mean IC +0.166, 80% positive IC fraction).
  - Out-of-Sample (2023–2024): Moderated to +4.37% ann. (Sharpe 0.47, Max DD 10.29%).
  - **Failure Reason:** While drawdown and turnover were tightly managed, net Sharpe of 0.47 fell short of the $\ge 1.0$ promotion bar.

---

## Architectural & Capital Boundary Verification

1. **Default-Deny Invariants:**
   - Zero execution components (`TradeIntent`, `BrokerAdapter`, `PaperTradingEngine`) were imported by the factor research module.
   - All tests run strictly on read-only historical price matrices.
2. **Fail-Closed Governance:**
   - In accordance with the Project TITAN Agent Constitution, all three factor hypotheses have terminated into absorbing `negative_result` records in `research/equities/results/`. No parameter snooping or retroactive gate relaxation occurred.
