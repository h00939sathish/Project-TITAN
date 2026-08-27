# FX-001: Passive MAE Excursion Reversal on London Opening Session (Pre-Registration)

- **Hypothesis ID:** `FX-001`
- **Governing ADRs:** ADR-014 (Forex Simulation), ADR-018 (IBKR Execution), ADR-031 (Canonical FX Simulation Costs).
- **Mechanism Ref:** [`M-003` (Structural Excursion Asymmetry — MEI = 0.85)](file:///D:/projects/Project%20TITAN/docs/MECHANISM_REGISTRY.md#L87-L110)
- **Status:** Sealed Pre-Registration (Evaluated across `EURUSD` and `GBPUSD`).

---

## 1. Economic Mechanism & Research Objectives

**Mechanism (`M-003`):** During London opening sessions (07:00–09:00 UTC), initial opening range breakouts trigger market maker inventory imbalances, creating an asymmetric mean-reverting excursion where Maximum Adverse Excursion (MAE) exceeds Maximum Favorable Excursion (MFE).

**Core Scientific Question:** Does a fixed, ex-ante $1.0 \times \text{Opening Range}$ adverse boundary provide an executable, profitable passive limit entry that survives institutional IBKR execution friction?

---

## 2. Decoupled Sub-Hypotheses & Evaluation Framework

```
                                    FX-001 Hypothesis Pipeline
  ┌────────────────────────────────────────────────────────┐
  │ Q1: Descriptive Replication                            │
  │     Does MAE > MFE replicate OOS (Wilcoxon p < 0.05)?  │
  └───────────────────────────┬────────────────────────────┘
                              │
  ┌───────────────────────────┴────────────────────────────┐
  │ Q2: Ex-Ante Boundary Predictability                    │
  │     Q2a: Zero data after 07:30 UTC used in calculation.│
  │     Q2b: 1.0x OR beats random boundary baseline.       │
  └───────────────────────────┬────────────────────────────┘
                              │
  ┌───────────────────────────┴────────────────────────────┐
  │ Q3: Passive Fill Accessibility & Adverse Selection     │
  │     P(Fill) ≥ 40% & Post-fill MAE ≤ 2.0x OR.           │
  └───────────────────────────┬────────────────────────────┘
                              │
  ┌───────────────────────────┴────────────────────────────┐
  │ Q4: Net Economic Expectancy & Cost Survivability       │
  │     Expectancy ≥ +1.5 pips after $4.00 round-trip fee. │
  │     Report Realized P&L vs Opportunity P&L.            │
  └────────────────────────────────────────────────────────┘
```

---

## 3. Exact Mathematical Formulations & Execution Protocol

### A. Exact MAE / MFE Calculation (Q1)
- **Reference Price:** $\text{Close}_{07:30\text{ UTC}}$ (after the initial 30m opening range).
- **Measurement Window:** 07:31 to 15:00 UTC.
- **Breakout Direction:** $\text{sign}(\text{Close}_{07:30} - \text{Open}_{07:00})$.

$$\text{For Long Breakouts } (\text{Close}_{07:30} > \text{Open}_{07:00}): \quad \begin{cases}
\text{MAE} = \max\left(0, \text{Close}_{07:30} - \min_{t \in [07:31, 15:00]} \text{Bid}_t\right) \\
\text{MFE} = \max\left(0, \max_{t \in [07:31, 15:00]} \text{Ask}_t - \text{Close}_{07:30}\right)
\end{cases}$$

$$\text{For Short Breakouts } (\text{Close}_{07:30} < \text{Open}_{07:00}): \quad \begin{cases}
\text{MAE} = \max\left(0, \max_{t \in [07:31, 15:00]} \text{Ask}_t - \text{Close}_{07:30}\right) \\
\text{MFE} = \max\left(0, \text{Close}_{07:30} - \min_{t \in [07:31, 15:00]} \text{Bid}_t\right)
\end{cases}$$

---

### B. Quantitative Entry Boundary (Q2)
- Evaluated strictly at **07:30:00 UTC** (zero future lookahead):
  $$\text{OR Range} = \max_{t \in [07:00, 07:30]}(\text{High}_t) - \min_{t \in [07:00, 07:30]}(\text{Low}_t)$$
  $$P_{\text{limit}} = \begin{cases}
  \text{Open}_{07:00} - 1.0 \times \text{OR Range} & \text{if Long Breakout (Buy Limit below open)} \\
  \text{Open}_{07:00} + 1.0 \times \text{OR Range} & \text{if Short Breakout (Sell Limit above open)}
  \end{cases}$$

---

### C. Simulated Post-Only Fill & Adverse Selection Model (Q3)
- Order submitted as **Post-Only Limit** at 07:30 UTC for $100,000$ base units ($1.0$ standard lot).
- **Fill Conditions (07:31 to 14:59 UTC):**
  - Buy Limit fills on bar $t$ if $\text{Ask}_t \le P_{\text{limit}}$.
  - Sell Limit fills on bar $t$ if $\text{Bid}_t \ge P_{\text{limit}}$.
- **Adverse Selection Telemetry:**
  - Fill Rate $\mathbb{P}(\text{Fill})$ (Must be $\ge 40.0\%$).
  - Median Time-to-Fill.
  - $\text{Post-Fill MAE}$: Maximum adverse movement experienced *after* the fill event.
  - Adverse Runaway Rate: Fraction of filled trades where $\text{Post-Fill MAE} > 2.0 \times \text{OR}$ (Must be $< 25\%$).

---

### D. Exit Rules & Canonical Institutional Cost Accounting (Q4)
- **Position Exit:** Mandatory market close at **15:00 UTC** ($\text{Bid}_{\text{exit}}$ for Longs, $\text{Ask}_{\text{exit}}$ for Shorts).
- **Unfilled Orders:** Canceled at 15:00 UTC ($0.0$ realized PnL; opportunity cost logged).
- **Institutional Fee Schedule (ADR-031):**
  - $\$2.00$ minimum ticket fee on Entry $+$ $\$2.00$ minimum ticket fee on Exit $\implies \mathbf{\$4.00 \text{ minimum round-trip fee}}$.
  - Standard lot sizing ($100,000$ base units $\implies \approx \$108,000$ notional) incurs $0.20\text{ bps}$ commission ($\approx \$4.32$ round trip $\approx 0.40\text{ pips}$).
  - Slippage impact: $0.10\text{ bps}$ on top-of-book market exit.

---

## 4. Control Baseline: Random Boundary Comparison

The fixed $1.0 \times \text{OR}$ boundary is benchmarked against an exposure-matched **Random Boundary Baseline** drawn uniformly from $[0.5 \times \text{OR}, 1.5 \times \text{OR}]$ over $N=500$ Monte Carlo iterations.

---

## 5. Acceptance Criteria & Absorbing Boundary

| Gate | Acceptance Criteria | Failure Action |
|---|---|---|
| **Q1: Descriptive Asymmetry** | $\text{MAE} > \text{MFE}$ with paired Wilcoxon $p < 0.05$ (IS & OOS) | Absorbing `negative_result` |
| **Q2: Predictability** | $1.0 \times \text{OR}$ achieves higher net expectancy than Random Baseline | Absorbing `negative_result` |
| **Q3: Fill Accessibility** | $\mathbb{P}(\text{Fill}) \ge 40.0\%$ and Adverse Runaway $< 25.0\%$ | Absorbing `negative_result` |
| **Q4: Net Expectancy** | OOS Net Expectancy $\ge 1.5\text{ pips/trade}$, Net Sharpe $\ge 0.80$, Max DD $\le 15.0\%$ | Absorbing `negative_result` |

If any criterion fails, `FX-001` terminates permanently as an absorbing `negative_result` without post-hoc lookback mining.
