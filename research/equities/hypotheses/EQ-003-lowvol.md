# EQ-003 — Cross-Sectional Volatility-Adjusted Momentum

- **Status:** Preregistered under ADR-030.
- **Economic Mechanism:** Penalizes high-volatility, lottery-like sector swings and rewards steady risk-adjusted relative strength. Combines the classic low-volatility anomaly with medium-term trend persistence.
- **Quantitative Model:**
  - Rank the 13-asset universe by 12-1M momentum divided by 63-day realized volatility ($\text{Sharpe}_{\text{relative}}$).
  - Allocate $+16.67\%$ each to top 3 leaders, $-16.67\%$ each to bottom 3 laggards.
  - Rebalance monthly (every 21 trading days).
- **Mandatory Friction:**
  - Standard IBKR tier ($0.005/sh) + 1.0 bps bid-ask spread per turn.
  - 50 bps annual short borrow cost accrued daily on short leg.
