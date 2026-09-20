# EQ-006 — US Equities Turnover-Constrained Quality & Low-Vol Factor Pre-Registration

- **Hypothesis ID:** `EQ-006`
- **Factor Name:** `turnover_constrained_quality_lowvol`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Sealed Pre-Registration (Evaluated on Liquid US Equities & Sector ETF Universe).

---

## 1. Economic Hypothesis & Lineage

### Review of Prior Failures:
1. **`EQ-001` (12-1M Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.70 vs $\ge 1.0$ gate) due to momentum inversion during tech concentration / divergence regimes.
2. **`EQ-002` (5-Day Reversal):** Terminated into `negative_result` (OOS Net Sharpe -0.17) due to extreme monthly turnover (~414%/month) generating -2.64%/yr friction drag that destroyed the gross edge.
3. **`EQ-003` (Volatility-Adjusted Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.47 vs $\ge 1.0$ hurdle), demonstrating that scaling inverted momentum by rolling volatility alone was insufficient to achieve the required hurdle.

### EQ-006 Mechanism & Independent Theoretical Basis:
- **Low-Volatility Anomaly:** Empirical asset pricing literature demonstrates that lower-volatility equity instruments systematically deliver superior risk-adjusted returns relative to high-beta / high-volatility counterparts (Baker, Bradley, & Wurgler; Ang et al.).
- **Quality / Risk-Adjusted Consistency:** Pure low-volatility can become a proxy for interest-rate duration or bond-proxies during tightening cycles. Combining inverse realized volatility with risk-adjusted return consistency (rolling Sharpe / return-to-volatility proxy) rewards high-quality, stable earners while filtering out low-volatility structural laggards.
- **Turnover-Constrained Rebalance Deadband (Hysteresis Buffer):** Standard quantile ranking suffers from boundary churn where assets oscillating around the cutoff trigger repeated liquidation and re-acquisition. EQ-006 enforces an entry/exit deadband:
  - **Long Leg:** Enter only when score reaches top 20th percentile ($p \ge 0.80$); exit only if score drops below 40th percentile ($p < 0.60$).
  - **Short Leg:** Enter only when score drops to bottom 20th percentile ($p \le 0.20$); exit only if score rises above 40th percentile ($p > 0.40$).
  - **Target:** Enforces monthly turnover $\le 15.0\%$, eliminating friction drag while capturing factor premia.

---

## 2. Frozen Experimental Parameters

- **Universe ($N=13$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `XLE`, `XLV`, `XLI`, `XLU`, `XLP`, `XLY`, `XLB`, `TLT` (from `research/equities/manifests/us_equities_etf_v1.json`).
- **Signal Formulation:**
  - **Low-Volatility Score:** Inverse 63-day rolling realized daily return volatility:
    $$\text{Score}_{\text{lowvol}, i, t} = \frac{1}{\sigma_{i, t-63..t}}$$
  - **Quality Score:** 252-day return over 63-day volatility (risk-adjusted consistency):
    $$\text{Score}_{\text{quality}, i, t} = \frac{R_{i, t-21 \to t-252}}{\sigma_{i, t-63..t}}$$
  - **Composite Score:** Equal-weighted sum of cross-sectional z-scores:
    $$S_{i,t} = \text{cross\_sectional\_zscore}(0.5 \cdot Z(\text{Score}_{\text{lowvol}}) + 0.5 \cdot Z(\text{Score}_{\text{quality}}))$$
- **Portfolio Construction:**
  - Market-neutral (Dollar-neutral): Target $+50\%$ Long leg, $-50\%$ Short leg (Gross exposure = $1.0$, Net exposure = $0.0$).
  - Rebalance Frequency: 21 trading days (monthly cadence).
  - Execution Timing: Decision at $t$, execution at $t+1$ (strictly causal, zero lookahead).
  - Deadband Rules: Entry at 20th percentile (top 3 / bottom 3); exit threshold at 40th percentile (rank outside top 5 / bottom 5).
- **Partitions:**
  - **In-Sample (IS):** 2020-01-02 to 2022-12-31 (36 months).
  - **Out-of-Sample (OOS):** 2023-01-03 to 2024-12-31 (24 months).
- **Cost Scenarios (Layer 1 Discovery & Stressed):**
  1. `baseline_ibkr_pro_fixed`: $\$0.005$/share ($\$1.00$ min), $1.0$ bps spread, $0.5$ bps slippage, $50$ bps annual short borrow, $0.00$ bps regulatory fees.
  2. `stressed_adverse_us_equity`: $\$0.010$/share ($\$2.00$ min), $3.0$ bps spread, $1.5$ bps slippage, $150$ bps annual short borrow, $0.08$ bps regulatory fees.

---

## 3. Decision Gates & Acceptance Criteria

| Gate | Metric | Hurdle | Rationale |
|---|---|---|---|
| **Gate 1** | OOS Net Sharpe | $\ge 1.0$ | Core statistical hurdle for research promotion candidate |
| **Gate 2** | Rank IC Positive Fraction | $\ge 70\%$ | Factor monotonicity and temporal consistency |
| **Gate 3** | Mean Rank IC | $\ge 0.05$ | Minimum cross-sectional ranking predictive power |
| **Gate 4** | Monthly Turnover | $\le 20.0\%$ (Target $\le 15.0\%$) | Capacity and execution survivability constraint |
| **Gate 5** | Max Drawdown | $\le 12.0\%$ | Downside risk containment |
| **Gate 6** | Quantile Monotonicity | Top > Bottom & Ordered | Proof that factor ranks systematically track returns |
| **Gate 7** | Stressed Adverse Net Return | $> 0.0$ | Robustness against severe friction shock |
| **Gate 8** | Replication | `replicated=True` | Independent verification |

---

## 4. Outcome Categorization per AGENTS.md Rule 8

- **Candidate:** Passes all 8 gates $\implies$ qualifies for Layer 2 paper execution calibration.
- **Negative Result:** If any gate fails, terminates permanently into absorbing `negative_result` state. Categorized as:
  - `mechanism_failure`: Underlying Quality/Low-Vol theory has no predictive alpha, inverted IC, or violated quantile monotonicity.
  - `execution_constrained_rejection`: Gross economic spread exists but friction exceeds harvestable yield.
  - `overfit_regime_fragile`: Strategy passed In-Sample but failed Out-of-Sample.
