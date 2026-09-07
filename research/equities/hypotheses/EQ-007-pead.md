# EQ-007 — US Equities Post-Earnings Announcement Drift (PEAD) Pre-Registration

- **Hypothesis ID:** `EQ-007`
- **Factor Name:** `post_earnings_announcement_drift_42d`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Sealed Pre-Registration (Evaluated on Liquid US Equities & Sector ETF Universe).

---

## 1. Economic Hypothesis & Lineage

### Review of Prior Failures:
1. **`EQ-001` (12-1M Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.70 vs $\ge 1.0$ gate) due to momentum inversion during tech concentration and Magnificent 7 divergence regimes.
2. **`EQ-002` (5-Day Reversal):** Terminated into `negative_result` (OOS Net Sharpe -0.17) due to extreme monthly turnover (~414%/month) generating -2.64%/yr friction drag that completely destroyed the gross edge.
3. **`EQ-003` (Volatility-Adjusted Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.47 vs $\ge 1.0$ hurdle), demonstrating that scaling inverted momentum by rolling volatility alone was insufficient to achieve the required hurdle.
4. **`EQ-004` (5-Day Reversal on Core-7):** Terminated due to broken monotonicity and severe regime fragility (thrived in 2022 bear market, collapsed in 2023 tech trend).
5. **`EQ-005` (Regime-Gated Long-Side Reversal):** Terminated into `negative_result`.
6. **`EQ-006` (Turnover-Constrained Quality & Low-Vol):** Terminated into `negative_result` (OOS Net Sharpe -0.13) under mega-cap tech expansion.

### EQ-007 Mechanism & Independent Theoretical Basis:
- **Post-Earnings Announcement Drift (PEAD):** Empirical financial economics (Ball & Brown 1968; Bernard & Thomas 1989; Foster, Olsen, & Shevlin 1984; Livnat & Mendenhall 2006) demonstrates that stock prices do not instantaneously adjust to the full information content of corporate earnings surprises. Instead, prices exhibit persistent, multi-week drift in the direction of the announcement surprise.
- **Institutional Under-Reaction & Slow Re-Pricing:**
  - Large institutional asset managers face liquidity constraints and internal governance hurdles that prevent immediate capital reallocation.
  - Sell-side analysts revise earnings forecasts conservatively and incrementally to manage corporate relations and mitigate downside career risk.
  - Cognitive anchoring to historical valuation baselines leads market participants to under-react to fundamental step-changes in earnings power.
- **Low-Turnover Horizon Design:**
  - Unlike high-turnover weekly reversal strategies (EQ-002 / EQ-004) that churn capital every 5 days and suffer debilitating friction, PEAD exploits a multi-week horizon (~42 trading days / 2 calendar months).
  - Quarterly rebalancing matches the fundamental cadence of earnings reporting cycles (~63 trading days), locking monthly turnover strictly $\le 10.0\%-15.0\%/\text{month}$ and eliminating turnover friction drag.

---

## 2. Frozen Experimental Parameters

- **Universe:** Liquid US Equities & ETFs from `research/equities/manifests/us_core_7_equities_v1.json` (`SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT`) and sector ETF universe.
- **Signal Formulation:**
  - **Quarterly Earnings Event Cadence:** Earnings surprises evaluated at quarterly event dates ($t_{\text{event}}$ spaced every ~63 trading days / 4 quarters per year).
  - **Standardized Unexpected Event Jump (SUE Proxy):**
    $$\text{Jump}_{i, t_{\text{event}}} = \frac{P_{i, t_{\text{event}}} - P_{i, t_{\text{event}}-1}}{P_{i, t_{\text{event}}-1}} - R_{\text{mkt}, t_{\text{event}}}$$
    where $R_{\text{mkt}, t_{\text{event}}}$ is the benchmark market return (SPY).
  - **Volatility Normalization:** Standardized by pre-event 63-day rolling daily return volatility:
    $$SUE_{i, t_{\text{event}}} = \frac{\text{Jump}_{i, t_{\text{event}}}}{\sigma_{i, t_{\text{event}}-63..t_{\text{event}}-1}}$$
  - **Cross-Sectional Standard Score:**
    $$S_{i, t_{\text{event}}} = \text{cross\_sectional\_zscore}(SUE_{i, t_{\text{event}}})$$
  - **Multi-Week Drift Persistence:** The standardized surprise signal $S_{i, t_{\text{event}}}$ is held point-in-time over the 42 trading day drift holding window ($t \in [t_{\text{event}}+1, t_{\text{event}}+42]$).
- **Portfolio Construction:**
  - Market-Neutral (Dollar-Neutral): Target $+50\%$ Long leg (Top $K=2$ positive surprise stocks), $-50\%$ Short leg (Bottom $K=2$ negative surprise stocks). Gross exposure = $1.0$, Net dollar exposure = $0.0$.
  - Holding Horizon: 42 trading days per earnings cycle.
  - Execution Timing: Decision at $t_{\text{event}}$, execution at $t_{\text{event}}+1$ (strictly causal, point-in-time, zero lookahead).
- **Partitions:**
  - **In-Sample (IS):** 2020-01-02 to 2022-12-31 (36 months).
  - **Out-of-Sample (OOS):** 2023-01-03 to 2024-12-31 (24 months).
- **Cost Scenarios (Layer 1 Discovery & Stressed):**
  1. `baseline_ibkr_pro_fixed`: $\$0.005$/share ($\$1.00$ min), $1.0$ bps spread, $0.5$ bps slippage, $50$ bps annual short borrow, $0.04$ bps regulatory fees.
  2. `stressed_adverse_us_equity`: $\$0.010$/share ($\$2.00$ min), $3.0$ bps spread, $1.5$ bps slippage, $150$ bps annual short borrow, $0.08$ bps regulatory fees.

---

## 3. Decision Gates & Acceptance Criteria

| Gate | Metric | Hurdle | Rationale |
|---|---|---|---|
| **Gate 1** | OOS Net Sharpe | $\ge 1.0$ | Core statistical hurdle for research candidate promotion |
| **Gate 2** | Rank IC Positive Fraction | $\ge 70\%$ | Factor directional stability and temporal consistency |
| **Gate 3** | Mean Rank IC | $\ge 0.05$ | Minimum cross-sectional ranking predictive power |
| **Gate 4** | Monthly Turnover | $\le 15.0\%$ (Target $\le 10.0\%$) | Capacity and low-turnover execution constraint |
| **Gate 5** | Max Drawdown | $\le 12.0\%$ | Downside risk containment |
| **Gate 6** | Quantile Monotonicity | Top > Bottom & Ordered | Proof that positive surprises systematically beat negative surprises |
| **Gate 7** | Stressed Adverse Net Return | $> 0.0$ | Robustness against severe friction shock |
| **Gate 8** | Replication | `replicated=True` | Independent verification |

---

## 4. Outcome Categorization per AGENTS.md Rule 8

- **Candidate:** Passes all 8 gates $\implies$ qualifies for Layer 2 paper execution calibration.
- **Negative Result:** If any gate fails, terminates permanently into absorbing `negative_result` state. Categorized as:
  - `mechanism_failure`: Underlying PEAD theory lacks predictive alpha, exhibits inverted IC, or violates quantile monotonicity.
  - `execution_constrained_rejection`: Gross economic spread exists but friction exceeds harvestable yield.
  - `overfit_regime_fragile`: Strategy passed In-Sample but failed Out-of-Sample.
