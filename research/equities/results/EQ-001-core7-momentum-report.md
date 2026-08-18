# EQ-001: US Equities Cross-Sectional Momentum Experiment Report

- **Experiment ID:** `EQ-001`
- **Governing ADR:** ADR-030 (Proposed & Under Research Evaluation)

- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT`
- **Signal:** 12-1 Month Momentum ($R_{t-21} / R_{t-252} - 1$, Cross-Sectional Z-Score)
- **Portfolio Construction:** Long Top 2 ($+50\%$), Short Bottom 2 ($-50\%$), Monthly Rebalance ($21$ trading days)
- **Cost Model:** $\$0.005$/share commission, $1.0$ bps spread, $0.5$ bps impact, $50$ bps annual short borrow

---

## 1. Executive Performance & Scientific Scorecard

| Metric | In-Sample (2020–2022) | Out-of-Sample (2023–2024) | Full Period (2020–2024) |
|---|---|---|---|
| **Annualized Net Return** | **-0.34%** | **-6.94%** | **-3.64%** |
| **Annualized Net Sharpe** | **-0.02** | **-0.56** | **-0.29** |
| **Max Drawdown** | 28.69% | 22.67% | 28.69% |
| **Monthly Turnover** | 18.06% | 26.20% | 22.13% |
| **Mean Rank IC (Spearman)** | **-0.040** | **-0.182** | **-0.111** |
| **Positive IC Fraction** | 42.9% | 39.1% | 41.0% |
| **Equal-Weight Long-Only Sharpe** | 0.52 | 1.86 | — |

---

## 2. Quantile Monotonicity & Leg Breakdown

### Quantile Performance (Annualized)
* **Top 2 (Long Target):** **+17.38%**
* **Middle 3 (Neutral):** **+23.68%**
* **Bottom 2 (Short Target):** **+30.25%**
* **Strict Monotonicity ($Top > Mid > Bottom$):** **VIOLATED**

### Leg Decomposition
| Period | Long Leg Contribution | Short Leg Contribution | Gross Spread | Net After Friction |
|---|---|---|---|---|
| **In-Sample (2020–2022)** | +9.13% | -9.03% | +0.10% | **-0.34%** |
| **Out-of-Sample (2023–2024)** | +18.62% | -25.17% | -6.55% | **-6.94%** |

---

## 3. Friction & Cost Attribution

| Cost Component | In-Sample (3 Years) | Out-of-Sample (2 Years) | Annual Drag |
|---|---|---|---|
| **Short Borrow (50 bps p.a.)** | -1.22% | -0.68% | ~0.25% / yr |
| **Commissions ($0.005/sh)** | -0.03% | -0.03% | ~0.08% / yr |
| **Execution Spread (1.0 bps)** | -0.07% | -0.06% | ~0.16% / yr |
| **Total Drag** | -1.31% | -0.77% | **~0.49% / yr** |

---

## 4. Regime Breakdown Across Market Cycles

| Year | Regime | Factor Net Return | Factor Net Sharpe | Max DD | Mean Rank IC | EW Benchmark Return |
|---|---|---|---|---|---|---|
| **2020** | COVID Crash & Rapid Rebound | +12.94% | 0.70 | 12.91% | +0.161 | +37.57% |
| **2021** | Broad Economic Reopening Bull | -20.68% | -1.89 | 20.62% | -0.123 | +29.81% |
| **2022** | Rate Hiking / Bear Market | -4.20% | -0.36 | 14.49% | -0.101 | -22.48% |
| **2023** | Mega-Cap Tech Concentration | -11.75% | -1.02 | 22.67% | -0.114 | +34.10% |
| **2024** | Broad Equity Expansion | -4.22% | -0.45 | 10.71% | -0.117 | +22.50% |

---

## 5. Core Scientific Verdict

> [!IMPORTANT]
> **Verdict: NEGATIVE RESULT (Signal Failure / Inverted Monotonicity on 7-Asset Universe)**
> - **Inverted Quantile Structure:** Over the 2020–2024 period on this 7-asset universe, the Bottom 2 12-1M laggards (+30.25% ann.) systematically outperformed the Top 2 leaders (+17.38% ann.), completely inverting the cross-sectional momentum hypothesis.
> - **Negative Rank IC:** Mean Spearman Rank IC was negative across both In-Sample (-0.040) and Out-of-Sample (-0.182), failing in 4 out of 5 annual regimes (2021, 2022, 2023, 2024). Only 2020 exhibited positive momentum predictive power (+0.161).
> - **Short-Leg Drag:** In OOS, while the long leg gained +18.62%, the short leg suffered -25.17% due to cyclical catch-up rallies in beaten-down assets, driving OOS Net Sharpe to -0.56.
> - **Friction vs Mechanism:** Transaction friction was modest (~0.49%/year drag on ~22% monthly turnover). The strategy failure is a **fundamental predictive mechanism failure** on this 7-asset universe, not an execution drag problem.
> - **Epistemic Scope & Boundary:** This result strictly rejects the 12-1 momentum formulation on this specific 7-asset ETF/mega-cap universe over 2020–2024. It does **not** claim that cross-sectional momentum is universally invalid across broad equity markets. In this concentrated basket, common macro drivers caused powerful cyclical mean-reversion in historical laggards.
> - **Zero Parameter Mining:** Per the TITAN Agent Constitution, we do not sweep alternative lookback windows (6-1, 3-1, 9-1) to rescue the hypothesis. `EQ-001` is permanently closed and archived. The unexpected laggard outperformance motivates a separate, clean reversal hypothesis (`EQ-002`).


