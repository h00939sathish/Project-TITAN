# EQ-004: US Equities 5-Day Cross-Sectional Short-Term Reversal Report

- **Experiment ID:** `EQ-004`
- **Factor:** 5-Day Short-Term Reversal ($R_{t-5 	o t}$ Contrarian Score)
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Cost Provenance)
- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT`
- **Rebalance Frequency:** 5 trading days (weekly) with 1-day execution lag ($t+1$)
- **Outcome Classification:** **Case D / Monotonicity Failure (Quantile Monotonicity Violated & Sub-Hurdle Sharpe — Absorbing Negative Result)**

---

## 1. Multi-Venue Execution Sensitivity Matrix (Out-of-Sample: 2023–2024)

| Metric | Baseline Alpaca (L1 Discovery) | Baseline IBKR Pro Tiered (L1 Discovery) | Stressed Adverse (L1 Adversarial) |
| :--- | :--- | :--- | :--- |
| **Gross OOS Spread (Ann.)** | **+3.23%** | **+3.23%** | **+3.23%** |
| **Commission Drag (Ann.)** | -0.00% | -0.19% | -0.53% |
| **Bid/Ask Spread Drag (Ann.)** | -0.53% | -0.42% | -1.59% |
| **Slippage Impact Drag (Ann.)** | -0.26% | -0.16% | -0.79% |
| **Short Borrow Drag (Ann.)** | -0.44% | -0.44% | -1.32% |
| **Total Friction Drag (Ann.)** | -1.25% | -1.23% | -4.27% |
| **Net OOS Annual Return** | **+1.97%** | **+1.99%** | **-1.07%** |
| **Net OOS Sharpe** | **0.18** | **0.18** | **-0.10** |
| **Max Drawdown** | 14.54% | 14.52% | 16.85% |
| **Monthly Turnover** | 443.3% | 443.3% | 443.3% |
| **Mean Rank IC (Spearman)** | **+0.034** | **+0.034** | **+0.034** |

---

## 2. In-Sample vs. Out-of-Sample Performance Breakdown (IBKR Pro Baseline)

| Metric | In-Sample (2020–2022) | Out-of-Sample (2023–2024) | Random Control Baseline (OOS) |
| :--- | :--- | :--- | :--- |
| **Gross Spread (Ann.)** | +7.97% | +3.23% | -0.51% |
| **Net Return (Ann.)** | +6.81% | +1.99% | -0.51% |
| **Net Sharpe Ratio** | **0.44** | **0.18** | **-0.05** |
| **Mean Rank IC** | **-0.024** | **+0.034** | **+0.006** |
| **Positive IC Fraction** | 50.3% | 49.0% | ~50.0% |

---

## 3. Quantile Monotonicity Verification

* **Top 2 (Long Target — Oversold Laggards):** **+30.96%**
* **Middle 3 (Neutral):** **+19.52%**
* **Bottom 2 (Short Target — Overbought Leaders):** **+21.97%**
* **Monotonic Ordering ($Top > Mid > Bot$):** **VIOLATED**

---

## 4. Annual Regime Breakdown (IBKR Pro Baseline)

| Year | Market Regime Context | Gross Spread | Net Return | Net Sharpe | Rank IC |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2020** | COVID Shock & Fast Rebound | +5.87% | +4.65% | 0.24 | -0.015 |
| **2021** | Economic Reopening Rally | +13.46% | +12.24% | 1.18 | -0.001 |
| **2022** | Inflation & Rate Hiking Bear | +23.32% | +22.21% | 1.56 | +0.009 |
| **2023** | Mega-Cap Tech Concentration | -2.86% | -4.02% | -0.36 | -0.069 |
| **2024** | Broad Bull Expansion | +9.00% | +7.70% | 0.70 | +0.144 |

---

## 5. Scientific Governance Verdict

1. **Outcome:** `Case D / Monotonicity Failure (Quantile Monotonicity Violated & Sub-Hurdle Sharpe — Absorbing Negative Result)`
2. **Economic Friction Sensitivity:** Weekly rebalance turnover is approximately **443.3%/month**, imposing an annual friction drag of **~1.23%/yr** under IBKR and **~1.25%/yr** under Alpaca.
3. **Absorbing Boundary:** Result is permanently archived in `EQ-004-core7-evidence-bundle.json`.
