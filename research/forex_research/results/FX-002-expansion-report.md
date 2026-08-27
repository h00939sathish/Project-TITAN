# FX-002: Asian Compression to London Volatility Expansion Report

- **Experiment ID:** `FX-002`
- **Mechanism Ref:** `M-006` (Session-Transition Volatility Expansion)
- **Instrument:** `EURUSD` (Dukascopy 1-minute Point-in-Time Bid/Ask Bars)
- **Outcome Classification:** **Case C — Spurious Trading Result (Gate 1 Volatility Expansion Failed)**

---

## 1. Gate 1: Volatility Expansion Phenomenon Test

| Partition | Compressed Days ($N$) | Non-Compressed Days ($N$) | Mean Compressed London Range | Mean Non-Compressed London Range | Difference | Welch's $t$-test $p$-value | Gate 1 Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **In-Sample (2021–2024)** | 98 | 419 | **59.1 pips** | 66.0 pips | **-6.9 pips** | $p = 0.981208$ | **FAILED** |
| **Out-of-Sample (2024–2026)** | 97 | 310 | **47.5 pips** | 51.8 pips | **-4.3 pips** | $p = 0.950429$ | **FAILED** |

---

## 2. Gate 2 & 4: Breakout Trading Performance (IBKR $4.00 Round-Trip Floor)

| Metric | Compressed Breakout (IS) | Unconditioned Breakout (IS) | Compressed Breakout (OOS) | Unconditioned Breakout (OOS) | Random Direction Baseline (OOS) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Total Sessions** | 517 | 517 | 407 | 407 | 407 |
| **Executed Trades** | 98 | 476 | 90 | 349 | 90 |
| **Trade Frequency** | 19.0% | 92.1% | 22.1% | 85.8% | — |
| **Win Rate** | 37.8% | 46.0% | 40.0% | 45.0% | — |
| **Net Pips / Trade** | **+0.66 pips** | +0.86 pips | **-0.54 pips** | -1.26 pips | -0.25 pips (+/- 1.15) |
| **Total Net USD** | **$+650.45** | $+4,081.11 | **$-488.97** | $-4,385.68 | — |
| **Annualized Sharpe** | **0.19** | 0.40 | **-0.19** | -0.69 | -0.29 |
| **Max Drawdown** | $1,936.42 | $7,212.65 | $2,076.97 | $7,824.78 | — |

---

## 3. Decision Gate Summary

1. **Gate 1 (Volatility Expansion Phenomenon):** **FAILED** — Realized range on compressed days vs non-compressed days.
2. **Gate 2 (Compression Filter Value-Add):** **PASSED** — Compressed Sharpe vs Unconditioned Sharpe.
3. **Gate 3 (Timestamp-Matched Random Superiority):** **FAILED** — Breakout direction vs Random entry at same timestamp.
4. **Gate 4 (Net Economic Hurdle):** **FAILED** — OOS Net Sharpe $\ge 0.80$, Expectancy $\ge 2.0	ext-1.0432973888890735$.

---

## 4. Scientific Governance Verdict

**Verdict:** `Case C — Spurious Trading Result (Gate 1 Volatility Expansion Failed)`  
Archived permanently in `FX-002-evidence-bundle.json`.
