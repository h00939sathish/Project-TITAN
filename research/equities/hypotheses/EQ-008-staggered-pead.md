# EQ-008 — Broad Universe Staggered Post-Earnings Announcement Drift (PEAD) Pre-Registration

- **Hypothesis ID:** `EQ-008`
- **Factor Name:** `staggered_post_earnings_announcement_drift_42d`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Sealed Pre-Registration (Evaluated on Broad 50-Stock US Liquid Universe `us_sp50_liquid_v1`).

---

## 1. Economic Hypothesis & Lineage

### Review of Prior Lineage & Failures:
1. **`EQ-001` (12-1M Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.70 vs $\ge 1.0$ gate) due to momentum inversion during tech concentration and Magnificent 7 divergence regimes.
2. **`EQ-002` (5-Day Reversal):** Terminated into `negative_result` (OOS Net Sharpe -0.17) due to extreme monthly turnover (~414%/month) generating -2.64%/yr friction drag that completely destroyed gross edge.
3. **`EQ-003` (Volatility-Adjusted Momentum):** Terminated into `negative_result` (OOS Net Sharpe 0.47 vs $\ge 1.0$ hurdle).
4. **`EQ-004` (5-Day Reversal on Core-7):** Terminated due to broken monotonicity and severe regime fragility.
5. **`EQ-005` (Regime-Gated Long-Side Reversal):** Terminated into `negative_result`.
6. **`EQ-006` (Turnover-Constrained Quality & Low-Vol):** Terminated into `negative_result` (OOS Net Sharpe -0.13) under mega-cap tech expansion.
7. **`EQ-007` (Core-7 Synchronized PEAD):** Validated strong underlying economic edge (gross spread +11.9%, net return +11.5%, Sharpe 1.25, Rank IC 0.174, strictly monotonic quantiles Top 41.1% vs Mid 29.2% vs Bot 10.1%), but **failed turnover capacity gates** (monthly turnover 18.1% vs 15.0% limit, target 10.0%) and IC positive consistency (62.5% vs 70.0% hurdle) due to synchronized rebalancing spikes across an overly concentrated 7-asset cluster.

### EQ-008 Staggered Mechanism & Broad Universe Formulation:
- **Broad Cross-Sectional Information Diffusion:** Expanding to a 50-stock diversified large-cap universe (`us_sp50_liquid_v1`) spans Tech, Financials, Healthcare, Consumer, Energy, and Industrials.
- **Staggered Earnings Event Distribution:**
  - In reality, corporate earnings releases are not synchronized on a single day. Instead, companies report across the 13 weeks (~63 trading days) of each quarterly earnings season.
  - Assigning each asset to its quarterly announcement date distributes rebalancing events continuously throughout the quarter (approx 1 asset reporting every 1.26 trading days, or 10 cohorts spaced 6 days apart).
- **Turnover Suppression via Staggered Holding Overlays:**
  - On any given trading day, only the ~1-2 assets reporting earnings update their standardized unexpected earnings (SUE) surprise signal and enter the 42-day drift holding window.
  - The remaining 48 assets remain in their established multi-week holding trajectory or neutral quiet period.
  - Portfolio turnover is smoothed continuously rather than concentrated in violent quarterly spikes, reducing monthly portfolio turnover strictly below $8.0\% - 10.0\%/\text{month}$.
- **Decile/Quintile Monotonicity & Robustness:**
  - With 50 liquid assets, cross-sectional ranking supports robust quintile/decile sorting ($K=10$ top long, $K=10$ bottom short), verifying whether alpha is monotonically ordered from extreme positive surprises to extreme negative surprises.

---

## 2. Frozen Experimental Parameters

- **Universe:** `research/equities/manifests/us_sp50_liquid_v1.json` (50 liquid US large-cap equities).
- **Signal Formulation:**
  - **Staggered Quarterly Announcement Schedule:** Each asset $i \in [0, 49]$ has a deterministic quarterly reporting cadence with event dates $t_{\text{event}, i} = t_{0, i} + k \times 63$, where $t_{0, i} = \lfloor i \times 63 / 50 \rfloor$.
  - **Standardized Unexpected Event Jump (SUE Proxy):**
    $$\text{Jump}_{i, t_{\text{event}, i}} = \frac{P_{i, t_{\text{event}, i}} - P_{i, t_{\text{event}, i}-1}}{P_{i, t_{\text{event}, i}-1}} - R_{\text{mkt}, t_{\text{event}, i}}$$
    where $R_{\text{mkt}, t}$ is the cross-sectional universe mean return (or SPY benchmark return).
  - **Volatility Normalization:** Standardized by pre-event 63-day rolling daily idiosyncratic volatility (lagged 1 day to strictly eliminate lookahead):
    $$\text{SUE}_{i, t_{\text{event}, i}} = \frac{\text{Jump}_{i, t_{\text{event}, i}}}{\sigma_{i, t_{\text{event}, i}-63..t_{\text{event}, i}-1}}$$
  - **Cross-Sectional Standard Score & Horizon Holding:**
    $$S_{i}(t) = \text{cross\_sectional\_zscore}(\text{SUE}_{i, t_{\text{event}, i}})$$
    Active for 42 trading days: $t \in [t_{\text{event}, i}, t_{\text{event}, i} + 41]$. Outside the 42-day drift window, $S_i(t) = 0.0$.
- **Portfolio Construction:**
  - Dollar-Neutral (Net exposure = $0.0$, Gross exposure = $1.0$).
  - Target: $+50\%$ Long leg (Top $K=10$ positive surprise assets), $-50\%$ Short leg (Bottom $K=10$ negative surprise assets).
  - Deadband Retention: Retain existing longs if percentile rank $\ge 0.40$; retain existing shorts if percentile rank $\le 0.60$.
  - Holding Horizon: 42 trading days per asset.
  - Execution Timing: Decision at $t$, execution at $t+1$ (strictly causal, point-in-time).
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
| **Gate 4** | Monthly Turnover | $\le 12.0\%$ (Target $\le 10.0\%$) | Capacity and low-turnover execution constraint via staggered rebalancing |
| **Gate 5** | Max Drawdown | $\le 12.0\%$ | Downside risk containment |
| **Gate 6** | Quantile Monotonicity | Top > Mid > Bottom & Ordered | Proof that positive surprises systematically beat negative surprises across quintiles/deciles |
| **Gate 7** | Stressed Adverse Net Return | $> 0.0$ | Robustness against severe friction shock |
| **Gate 8** | Replication | `replicated=True` | Independent verification |

---

## 4. Outcome Categorization per AGENTS.md Rule 8

- **Candidate:** Passes all 8 gates $\implies$ qualifies for Layer 2 paper execution calibration.
- **Negative Result:** If any gate fails, terminates permanently into absorbing `negative_result` state. Categorized as:
  - `mechanism_failure`: Underlying PEAD theory lacks predictive alpha, exhibits inverted IC, or violates quantile monotonicity.
  - `execution_constrained_rejection`: Gross economic spread exists but friction exceeds harvestable yield.
  - `overfit_regime_fragile`: Strategy passed In-Sample but failed Out-of-Sample.
