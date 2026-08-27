# FX-001: Passive MAE Excursion Reversal Research Report

- **Experiment ID:** `FX-001`
- **Mechanism Ref:** [`M-003` (Structural Excursion Asymmetry)](file:///D:/projects/Project%20TITAN/docs/MECHANISM_REGISTRY.md#L87-L110)
- **Instrument:** `EURUSD` (London Opening Session: 07:00–15:00 UTC)
- **Outcome Classification:** **Case D — Mechanism Failure (MAE > MFE Failed to Replicate OOS)**

---

## 1. Q1: Descriptive Replication Matrix (MAE > MFE Asymmetry)

| Partition | Sessions ($N$) | Mean MAE | Mean MFE | MAE/MFE Ratio | Fraction MAE > MFE | Wilcoxon $p$-value | Gate Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **In-Sample (2021–2024)** | 553 | 30.1 pips | 31.1 pips | **0.97x** | 48.1% | $p = 0.813303$ | **FAILED** |
| **Out-of-Sample (2024–2026)** | 411 | 22.9 pips | 25.9 pips | **0.89x** | 44.5% | $p = 0.967333$ | **FAILED** |

---

## 2. Q2–Q4: Passive Limit Order Execution Telemetry (1.0x OR Boundary)

| Metric | In-Sample (2021–2024) | Out-of-Sample (2024–2026) | Random Boundary Control (OOS N=500) |
| :--- | :--- | :--- | :--- |
| **Total Eligible Sessions** | 553 | 411 | 411 |
| **Filled Sessions** | 292 | 210 | — |
| **Fill Rate P(Fill)** | **52.8%** | **51.1%** | 51.9% |
| **Median Time-to-Fill** | 126 min | 135 min | — |
| **Post-Fill Mean MAE** | 26.6 pips | 19.5 pips | — |
| **Post-Fill Mean MFE** | 26.8 pips | 22.2 pips | — |
| **Adverse Runaway Rate (>2.0x OR)** | 36.3% | 34.3% | — |
| **Mean Net Expectancy / Trade** | **-2.62 pips** | **+1.32 pips** | +1.91 pips (+/- 0.62) |
| **Mean Net USD / Trade** | **$-26.20** | **$+13.18** | — |
| **Total Realized Net P&L** | **$-7,649.94** | **$+2,767.70** | — |
| **Unfilled Opportunity P&L** | $-1,037.50 | $+10,309.50 | — |
| **Annualized Net Sharpe** | **-0.79** | **0.60** | 0.84 |
| **Max Drawdown** | $11,181.83 | $2,616.24 | — |

---

## 3. Decision Gate Summary

1. **Q1 (Descriptive Asymmetry):** **FAILED** — Tested MAE vs MFE across all sessions.
2. **Q2b (Predictability vs. Random Baseline):** **FAILED** — Fixed 1.0x OR boundary comparison against Monte Carlo baseline.
3. **Q3 (Passive Fill Accessibility):** **FAILED** — Fill rate is **51.1%** with **34.3%** adverse runaway rate.
4. **Q4 (Net Economic Expectancy after Costs):** **FAILED** — Net expectancy is **+1.32 pips** (Sharpe **0.60**).

---

## 4. Scientific Governance Verdict

**Verdict:** `Case D — Mechanism Failure (MAE > MFE Failed to Replicate OOS)`  
Recorded permanently in `FX-001-evidence-bundle.json`.
