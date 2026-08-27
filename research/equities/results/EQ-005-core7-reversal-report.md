# EQ-005: US Equities Regime-Gated Long-Side Short-Term Reversal Report

- **Experiment ID:** `EQ-005`
- **Factor:** 5-Day Short-Term Reversal (Long Bottom 2 Laggards Only / 100% Cash when Inactive)
- **Primary Regime Variable:** 21-Day Rolling Cross-Sectional Dispersion $> 71.5	ext{ bps}$ (IS Median, Lagged $t-1$)
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Cost Provenance)
- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT`
- **Rebalance Frequency:** 5 trading days (weekly) with 1-day execution lag ($t+1$)
- **Outcome Classification:** **Case D — Regime Gating Ineffective / Redundant (Absorbing Negative Result)**

---

## 1. Multi-Venue Execution Sensitivity Matrix (Out-of-Sample: 2023–2024)

| Metric | Baseline Alpaca (L1 Discovery) | Baseline IBKR Pro Tiered (L1 Discovery) | Stressed Adverse (L1 Adversarial) |
| :--- | :--- | :--- | :--- |
| **Gross OOS Return (Ann.)** | **+71.77%** | **+71.77%** | **+71.77%** |
| **Commission Drag (Ann.)** | -0.00% | -0.01% | -0.02% |
| **Bid/Ask Spread Drag (Ann.)** | -0.02% | -0.01% | -0.05% |
| **Slippage Impact Drag (Ann.)** | -0.01% | -0.01% | -0.03% |
| **Total Friction Drag (Ann.)** | -0.03% | -0.03% | -0.10% |
| **Net OOS Annual Return** | **+71.74%** | **+71.74%** | **+71.67%** |
| **Net OOS Sharpe** | **1.63** | **1.63** | **1.63** |
| **Max Drawdown** | 33.86% | 33.86% | 33.86% |
| **Monthly Turnover** | 14.7% | 14.7% | 14.7% |
| **Active Days Fraction** | 88.8% | 88.8% | 88.8% |

---

## 2. In-Sample vs. Out-of-Sample Performance vs. Controls (IBKR Pro Baseline)

| Metric | In-Sample (2020–2022) | Out-of-Sample (2023–2024) | Unconditioned Long Reversal (OOS) | Random Selection Control (OOS) |
| :--- | :--- | :--- | :--- | :--- |
| **Gross Return (Ann.)** | +58.20% | +71.77% | +93.36% | +68.71% |
| **Net Return (Ann.)** | +58.18% | +71.74% | +93.35% | +68.71% |
| **Net Sharpe Ratio** | **0.72** | **1.63** | **1.83** | **1.60** ($\pm 0.07$) |
| **Max Drawdown** | 75.71% | 33.86% | 35.18% | — |
| **Active Market Exposure** | 94.6% | 88.8% | 100.0% | 88.8% |

---

## 3. Annual Regime Breakdown (IBKR Pro Baseline)

| Year | Market Regime Context | Gross Return | Net Return | Net Sharpe | Max DD | Active Exposure | SPY Benchmark |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2020** | COVID Crash & Sharp Rebound | +148.05% | +148.00% | 1.87 | 38.09% | 83.8% | +22.38% |
| **2021** | Broad Economic Reopening Rally | +106.07% | +106.03% | 2.07 | 19.31% | 99.6% | +26.11% |
| **2022** | Rate Hiking / Bear Dispersion | -37.81% | -37.85% | -0.49 | 57.40% | 91.6% | -17.20% |
| **2023** | Mega-Cap Tech Concentration | +72.49% | +72.44% | 1.96 | 31.43% | 77.6% | +24.30% |
| **2024** | Broad Bull Expansion | +53.87% | +53.81% | 1.21 | 33.86% | 79.7% | +23.48% |

---

## 4. Scientific Governance Verdict

1. **Outcome:** `Case D — Regime Gating Ineffective / Redundant (Absorbing Negative Result)`
2. **Key Attribution Insight:** Gating by lagged cross-sectional dispersion reduces market exposure to **88.8%** of trading days, mitigating turnover and drawdown relative to unconditioned factor models.
3. **Absorbing Boundary:** Evidence bundle archived in `EQ-005-core7-evidence-bundle.json`.
