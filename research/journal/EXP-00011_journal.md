# Research Journal Entry — EXP-00011

> **Experiment ID:** EXP-00011  
> **Canonical Research Question:** RQ-002 (Volatility Compression & Directional Expansion)  
> **Author:** TITAN Research OS  
> **Date:** 2026-07-30  
> **Status:** `REJECTED`

---

## 1. Hypothesis

Intraday volatility compression (periods where ATR drops into the bottom 25th percentile over a 100-bar rolling window) precedes clean directional price expansion (breakout magnitude > 2.0x ATR) with probability > 55%.

**Falsifiable claim:** Expansion breakout success rate following volatility compression > 55% in out-of-sample data with binomial p < 0.05.

---

## 2. Economic Mechanism

Proposed mechanism: Intraday liquidity drying (evidenced by low ATR) causes order accumulation without price movement, which is expected to trigger a thin-orderbook directional expansion sweep once completed.

---

## 3. Prediction

- **Primary:** Expansion breakout success rate > 55% with p < 0.05.
- **Secondary:** Whipsaw rate < 30%, Mean expansion ratio > 2.0x.

---

## 4. Methodology

- **Instruments:** SPY (equity index ETF), EURUSD (spot forex)
- **Timeframe:** 15-minute bars
- **Compression Definition:** 20-bar ATR < 25th percentile of 100-bar rolling window
- **Target Expansion:** > 2.0x ATR move in breakout direction before re-entering compression range
- **Split:** 60% Train / 40% OOS
- **Statistical Tests:** One-sided binomial test, cross-asset consistency.

---

## 5. Result

### SPY (238 events total: 142 Train / 96 OOS)

| Metric | Train (142 events) | OOS (96 events) |
|---|---|---|
| Expansion Success Rate | 6.3% (9/142) | **27.1% (26/96)** |
| False Breakout (Whipsaw) Rate | 23.2% | 27.1% |
| Mean Expansion Ratio | 0.65x | 1.13x |
| Binomial p-value | 1.0000 | **1.0000** |

### EURUSD (158 events total: 94 Train / 64 OOS)

| Metric | Train (94 events) | OOS (64 events) |
|---|---|---|
| Expansion Success Rate | 4.3% (4/94) | **7.8% (5/64)** |
| False Breakout (Whipsaw) Rate | 33.0% | 25.0% |
| Mean Expansion Ratio | 0.47x | 0.64x |
| Binomial p-value | 1.0000 | **1.0000** |

### Governance Gate

| Check | Result |
|---|---|
| SPY OOS Success Rate > 55% | ❌ FAIL (27.1%) |
| SPY OOS Binomial p < 0.05 | ❌ FAIL (p = 1.0000) |
| EURUSD OOS Success Rate > 55% | ❌ FAIL (7.8%) |
| EURUSD OOS Binomial p < 0.05 | ❌ FAIL (p = 1.0000) |
| Cross-Asset Consistency (> 50%) | ❌ FAIL (Both < 30%) |

---

## 6. Unexpected Observations

1. **Expansion Ratios are Muted:** Instead of expanding 2.0x ATR, price moves on average only **1.13x ATR** (SPY) and **0.64x ATR** (EURUSD) following compression.
2. **Compression Persists Longer Than Anticipated:** Low ATR windows frequently lead to extended low-volatility drift rather than immediate energetic expansion.

---

## 7. What We Now Believe

Naive volatility compression (ATR percentile alone) does **not** reliably predict directional expansion. Compression is a state of equilibrium, not an inherent spring-loaded precursor to trend expansion. To capture directional expansion, compression must be combined with a secondary catalyst (e.g. regime transition or volume shock).

---

## 8. Next Experiment

Preregister **EXP-00012** under **RQ-002**: Test whether adding a **Volume Shock Filter** (volume > 2.5x 20-bar SMA at the breakout point) converts muted compression into clean directional expansion.

---

## 9. Decision

**Decision:** `REJECTED`

**Justification:** OOS success rates (27.1% SPY, 7.8% EURUSD) failed the 55% threshold and binomial significance test (p = 1.0000).

**Evidence Bundle:** [`research/experiments/EXP-00011_evidence_bundle.json`](../experiments/EXP-00011_evidence_bundle.json)

**EQI Dimensions:**

| Dimension | Score |
|---|---|
| Reproducibility | 1.00 |
| Replication | 0.90 (SPY + EURUSD multi-asset pass) |
| Statistical Robustness | 0.90 (Large sample: 238 SPY + 158 EURUSD events) |
| Economic Plausibility | 0.85 |
| Execution Realism | 0.70 |
| Documentation | 1.00 |
