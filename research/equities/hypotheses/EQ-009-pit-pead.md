# EQ-009 — Point-in-Time Consensus Post-Earnings Announcement Drift (PEAD) Pre-Registration

- **Hypothesis ID:** `EQ-009`
- **Factor Name:** `point_in_time_pead_sue_42d`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Frozen Pre-Registration (Evaluated on Liquid US 50-Stock Universe with Point-in-Time Consensus Earnings).

---

## 1. Economic Hypothesis & Lineage

### Review of Prior Lineage:
1. **`EQ-007` (Core-7 PEAD):** Confirmed strong economic edge (+12.7% net return, 1.46 Sharpe, 0.27 rank IC, strictly monotonic quantiles) but failed turnover capacity gates because a 7-asset cluster concentrated rebalancing into violent quarterly turnover spikes.
2. **`EQ-008` (Staggered PEAD on SP50):** Attempted to smooth turnover by staggering cohorts on a broad 50-stock universe, but terminated into `negative_result` (OOS Sharpe -0.06) because it relied on a synthetic 63-day periodic price-jump proxy rather than true earnings announcement events.
3. **`EQ-Micro-001` (ETF Intraday Lead-Lag):** Terminated into `negative_result` (Net Sharpe -32.47) due to high turnover (568%/month) creating an insurmountable 759% friction drag under IBKR Pro fixed ticket fees.

### EQ-009 Mechanism & True Consensus Surprise:
- **Standardized Unexpected Earnings (SUE):**
  Stock prices exhibit multi-week drift following earnings releases due to institutional capital rebalancing delays and conservative analyst revisions.
  Instead of synthetic periodic price jumps, `EQ-009` uses verified point-in-time Wall Street analyst consensus EPS estimates and actual reported EPS:
  $$\text{SUE}_{i, q} = \frac{\text{ReportedEPS}_{i, q} - \text{EstimatedEPS}_{i, q}}{P_{i, t_{\text{eff}}-1}}$$
- **Exact Announcement Timing & Causal Alignment:**
  - Before Market Open (BMO): The surprise is known before trading begins; position is entered at $t_{\text{eff}} = t$.
  - After Market Close (AMC) or Weekend: The surprise is announced after trading hours; position is entered at $t_{\text{eff}} = t + 1$.
  - Zero lookahead: Pre-event price is strictly prior to announcement, and positions are held for 42 trading days.
- **Natural Staggering & Turnover Immunity:**
  Because real corporate earnings dates naturally disperse across the 13 weeks of quarterly earnings season, rebalancing occurs smoothly in small increments (1-2 names per week), maintaining monthly portfolio turnover strictly below $\le 10.0\%/\text{month}$.

---

## 2. Frozen Experimental Parameters

- **Universe:** 50 Liquid US Large-Cap Equities from `research/equities/manifests/us_sp50_earnings_pit_v1.json`.
- **Signal Formulation:**
  - On each company's verified announcement date, calculate price-deflated SUE:
    $$\text{SUE}_{i, t} = \frac{\text{ReportedEPS}_{i, t} - \text{EstimatedEPS}_{i, t}}{P_{i, t_{\text{eff}}-1}}$$
  - Standardize cross-sectionally across the active reporting universe.
  - Hold the surprise score constant across the 42-day drift window ($t \in [t_{\text{eff}}, t_{\text{eff}} + 41]$).
- **Portfolio Construction:**
  - Dollar-Neutral (Target Gross Exposure = 1.0, Net Dollar Exposure = 0.0).
  - Target Portfolio: Long Top 10 positive SUE names (+50%), Short Bottom 10 negative SUE names (-50%).
  - Deadband Retention: Retain existing longs if rank remains $\ge 40$th percentile; retain existing shorts if rank remains $\le 60$th percentile.
  - Holding Horizon: 42 trading days per earnings cycle.
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
| **Gate 1** | OOS Net Sharpe | $\ge 1.00$ | Sustainable economic excess return after IBKR Pro fixed ticket and borrow costs |
| **Gate 2** | IC Positive Fraction | $\ge 65.0\%$ | Alpha directional consistency across quarterly rebalancing cycles |
| **Gate 3** | Mean Rank IC | $\ge 0.030$ | Cross-sectional ranking power of SUE against 42-day forward drift |
| **Gate 4** | Quantile Monotonicity | Top > Bottom | Verifies monotonic returns across surprise deciles/quintiles |
| **Gate 5** | Max Drawdown Limit | $\le 15.0\%$ | Portfolio preservation under multi-year equity regimes |
| **Gate 6** | Monthly Turnover | $\le 15.0\%$/mo | Natural quarterly staggering preserves capital from fee churn |
| **Gate 7** | Stressed Adverse Net Return | $> 0.0\%$ | Survival under doubled commission ($0.01/sh), 3.0 bps spread, 150 bps borrow |

---

## 4. Terminal State Classification

- **Promotion Path:** If all 7 gates pass on the untouched OOS partition ($2023\text{--}2024$), `EQ-009` achieves **`candidate`** status eligible for Layer 2 paper execution shadow routing.
- **Failure Classification:** If any gate fails, terminates permanently into absorbing **`negative_result`** per ADR-029/030, categorized as either:
  - `mechanism_failure`: if Rank IC, IC positive fraction, or monotonicity fail.
  - `execution_constrained`: if gross alpha is positive but net returns fail due to borrow or ticket fees.
