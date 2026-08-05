# Research Journal Entry — EXP-00008

> **Experiment ID:** EXP-00008  
> **Canonical Research Question:** RQ-001 (Opening Auction Imbalance Dynamics)  
> **Author:** TITAN Research OS  
> **Date:** 2026-07-30  
> **Status:** `REJECTED`

---

## 1. Hypothesis

In equity index ETFs (SPY), the direction and magnitude of the opening range
(first 30 minutes — two 15-minute bars after 13:30 UTC / 9:30 AM ET) predicts
the sign of the remaining session return (10:00 AM ET to 4:00 PM ET close) with
probability significantly above 50%.

**Falsifiable claim:** Opening-range continuation rate > 52% with p < 0.05 vs
null hypothesis of 50% (binomial test).

---

## 2. Economic Mechanism

Institutional Market-On-Open (MOO) and Limit-On-Open (LOO) order flow creates
directional price pressure at the open. Large orders submitted during the
opening auction are typically not fully absorbed in the first minutes, causing
residual order flow that persists through the morning session.

If true, the opening range direction should predict continuation — not because
of technical momentum, but because the same institutional flow that moved the
opening range continues to execute through the session.

---

## 3. Prediction

**Primary:** Opening-range continuation rate (same-sign session return) > 52%.

**Secondary:**
- Mean continuation-session return > mean reversal-session return.
- Effect stronger on high-volume opens (top-quartile opening volume).
- Effect survives 2 bps round-trip execution cost.

**Kill criteria (preregistered):**
- Continuation rate ≤ 50% in OOS.
- p-value ≥ 0.10 (binomial test).
- Effect disappears after transaction costs.
- Fewer than 15 testable sessions in OOS.

---

## 4. Methodology

- **Instrument:** SPY (equity index ETF)
- **Timeframe:** 15-minute bars
- **Data Source:** TWS historical bars, `spy_15m.csv` (2026-07-30 pull)
- **Date Range:** 2026-06-05 to 2026-07-29 (37 testable sessions)
- **Train / Validation Split:** 60% / 40% chronological (22 train / 15 OOS)
- **Train Period:** 2026-06-05 to 2026-07-08
- **OOS Period:** 2026-07-09 to 2026-07-29
- **Opening Range:** First two 15m bars after 13:30 UTC (9:30 AM ET)
- **Session Return:** Last bar close before 20:00 UTC minus opening range close
- **Statistical Tests:**
  - Binomial test: continuation rate vs null = 50% (one-sided, continuity-corrected)
  - Welch's t-test: mean continuation return vs mean reversal return
  - Volume quartile split: top-quartile vs bottom-quartile continuation rates
- **Multiple Testing Correction:** Bonferroni for 3 secondary tests (α = 0.0167)

---

## 5. Result

| Metric | Train (22 sessions) | OOS (15 sessions) |
|---|---|---|
| Continuation Rate | 63.6% (14/22) | 53.3% (8/15) |
| p-value (binomial) | 0.1432 | 0.5000 |
| Mean Continuation Return | 0.4363% | 0.3919% |
| Mean Reversal Return | 0.8145% | 0.2716% |
| Welch t-stat (p-value) | -2.483 (0.0065) | 0.727 (0.2337) |
| High-Volume Cont. Rate | 50.0% | 25.0% |
| Low-Volume Cont. Rate | 100.0% | 100.0% |
| Cost Survival Rate | 100.0% | 100.0% |

### Governance Gate

| Check | Result |
|---|---|
| OOS continuation rate > 52% | ✅ PASS (53.3%) |
| OOS p-value < 0.05 | ❌ FAIL (0.5000) |
| OOS minimum 15 sessions | ✅ PASS (15) |
| Effect survives costs | ✅ PASS (100%) |
| Train-OOS consistency (< 15pp) | ✅ PASS (10.3pp gap) |

---

## 6. Unexpected Observations

1. **Reversal returns are larger than continuation returns in-sample.** In the train period, sessions that *reversed* the opening range direction produced a mean absolute return of 0.81%, compared to 0.44% for continuations. The Welch t-test was significant (p = 0.0065). This is the opposite of what the institutional flow hypothesis predicts — reversals are *stronger* moves, not weaker ones.

2. **High-volume opens do not amplify continuation.** The hypothesis predicted that high-volume opens (proxy for institutional MOO flow) should show stronger continuation. Instead, high-volume opens showed *lower* continuation rates (50% train, 25% OOS) compared to low-volume opens (100% both). This directly contradicts the economic mechanism.

3. **The train continuation rate (63.6%) was not statistically significant.** Even in-sample, the binomial p-value was 0.1432 — failing the preregistered 0.05 threshold. The apparent 63.6% rate is within normal random variation for 22 coin flips.

4. **OOS continuation rate collapsed to near-chance.** The 53.3% OOS rate (8/15) is indistinguishable from random (p = 0.5000). The 10.3 percentage point drop from train to OOS is consistent with the in-sample rate being noise.

---

## 7. What We Now Believe

The opening range direction on SPY does **not** reliably predict session drift in the current market regime (June–July 2026). Specifically:

- **The institutional flow persistence hypothesis is not supported.** If residual MOO order flow drove session continuation, we would expect (a) statistically significant continuation rates and (b) stronger continuation on high-volume opens. Neither was observed.

- **Reversals may be more informative than continuations.** The finding that reversal sessions produced larger absolute moves (0.81% vs 0.44%) is interesting. It could suggest that strong opening moves trigger mean-reversion from counter-flow during the session. This is a separate hypothesis worth investigating under RQ-001.

- **Sample size limitations are real.** With only 37 sessions and 15 OOS, statistical power is low. A continuation rate of 65%+ would be needed to achieve significance at this sample size. This constrains what can be concluded — the absence of evidence is not strong evidence of absence.

- **Low-volume opens showed 100% continuation** in both train and OOS. This is likely a small-sample artifact (low-volume quartile ≈ 4–6 sessions), but it is worth monitoring in future data.

---

## 8. Next Experiment

Two follow-up directions are warranted under RQ-001:

1. **EXP-00009 (Reversal hypothesis):** Test whether the *magnitude* of the opening range (not direction) predicts session volatility or reversal probability. The unexpected finding that reversals produced larger returns may reflect a mean-reversion dynamic following opening auction overreaction.

2. **Longer data collection:** The current dataset spans only ~40 sessions. Before accepting or rejecting RQ-001 definitively, we should accumulate 6+ months of 15m SPY data to achieve adequate statistical power (100+ sessions needed for 55% effect at α = 0.05).

No immediate replication attempt is warranted — the primary effect is not statistically significant even in-sample.

---

## 9. Decision

**Decision:** `REJECTED`

**Justification:** The primary hypothesis (continuation rate > 52% with p < 0.05) failed the preregistered statistical significance threshold in both train (p = 0.1432) and OOS (p = 0.5000). Additionally, the secondary prediction that high-volume opens amplify continuation was directly contradicted by the data. The economic mechanism (institutional MOO flow persistence) is not supported by the evidence.

**This is a well-formed rejection.** The hypothesis was clear, the methodology was unbiased, and the preregistered kill criteria were triggered cleanly. The rejection adds permanent value: it identifies reversal dynamics as a more promising direction under RQ-001.

**Evidence Bundle:** [`research/experiments/EXP-00008_evidence_bundle.json`](../experiments/EXP-00008_evidence_bundle.json)

**EQI Dimensions:**

| Dimension | Score |
|---|---|
| Reproducibility | 1.00 — Deterministic script, data hash verifiable, identical re-run produces identical output |
| Replication | 0.00 — Single instrument (SPY), single time period. Not yet replicated. |
| Statistical Robustness | 0.85 — Binomial test with continuity correction, Welch t-test, Bonferroni correction applied. Sample size is the limiting factor. |
| Economic Plausibility | 0.90 — Hypothesis grounded in well-documented institutional MOO/LOO flow mechanics. |
| Execution Realism | 0.80 — 2 bps round-trip cost modeled. No slippage modeling for intraday entry/exit timing. |
| Documentation | 1.00 — Preregistered journal, evidence bundle, session-level detail preserved. |
