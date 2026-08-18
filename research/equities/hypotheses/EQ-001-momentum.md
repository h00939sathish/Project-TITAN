# EQ-001 — Cross-Sectional 12-1M Momentum

- **Status:** Preregistered under ADR-030.
- **Economic Mechanism:** Medium-term price momentum driven by gradual information diffusion, underreaction to fundamental sector earnings growth, and institutional style-chasing flows across US sector ETFs.
- **Quantitative Model:**
  - Rank the 13-asset universe by cumulative return over the preceding 252 trading days, skipping the most recent 21 trading days (1 month).
  - Allocate $+1/6$ (+16.67%) weight to the top 3 highest-momentum ETFs and $-1/6$ (-16.67%) weight to the bottom 3 lowest-momentum ETFs.
  - Rebalance every 21 trading days (monthly).
- **Mandatory Friction:**
  - Standard IBKR tier ($0.005/sh) + 1.0 bps bid-ask spread per turn.
  - 50 bps annual short borrow cost accrued daily on short leg.
