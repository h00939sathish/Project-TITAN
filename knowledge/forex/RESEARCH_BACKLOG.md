# PROJECT TITAN — FOREX RESEARCH BACKLOG & CANONICAL RESEARCH QUESTIONS

> **Owner:** Quantitative Research Backlog Committee  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Research Pipeline & Experiment Harness  
> **Governance:** [CANONICAL_RESEARCH_QUESTIONS.md](file:///d:/projects/Project%20TITAN/docs/CANONICAL_RESEARCH_QUESTIONS.md)

---

## 1. Prioritized Forex Research Questions (RQs)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROJECT TITAN FOREX RESEARCH BACKLOG                     │
└─────────────────────────────────────────────────────────────────────────────┘
  ID           Research Title / Question                            Priority  Status
  ───────────────────────────────────────────────────────────────────────────
  RQ-FX-001    Volatility-Adjusted Carry Harvest Efficiency         P0        Ratified / In-Progress
  RQ-FX-002    WMR 4 PM London Fix Pre-Hedge Drift & Reversal       P1        Formulated
  RQ-FX-003    VPIN High-Frequency Toxicity as Execution Safeguard  P1        Formulated
  RQ-FX-004    Cross-Asset Yield Curve Spreads (OIS) as FX Alpha   P2        Backlog
  RQ-FX-005    COT Institutional Positioning Extreme Reversals     P2        Backlog
  RQ-FX-006    Temporal Fusion Transformer Intraday Trend Forecast P2        Research Phase
  RQ-FX-007    Cointegrated StatArb Pairs Spread Mean-Reversion    P1        Formulated
  RQ-FX-008    Almgren-Chriss Optimal TWAP Slicing vs Single Orders P0        Active / Verified
```

---

## 2. Detailed Formulation for Priority Research Questions

### RQ-FX-001: Volatility-Adjusted Carry Harvest Efficiency
- **Hypothesis:** Scaling long G10 carry positions inversely to 30-day realized volatility and suspending long carry exposure when global FX volatility ($\text{VXY}$) crosses its 90th percentile reduces maximum drawdown by $> 40\%$ without reducing long-term Sharpe ratio.
- **Data Required:** Daily Spot prices (`EURUSD`, `GBPUSD`, `AUDUSD`, `USDJPY`), OIS interest rate differentials, VXY index.
- **Acceptance Criteria:** Out-of-sample Sharpe ratio $> 0.85$, Max Drawdown $< 18\%$.

### RQ-FX-002: WMR 4 PM London Fix Pre-Hedge Drift & Reversal
- **Hypothesis:** Systematic pre-hedging order flow between 3:45 PM – 4:00 PM ET creates statistically significant directional momentum, followed by a mean-reverting snapback between 4:02 PM – 4:15 PM ET.
- **Data Required:** 1-minute intraday tick/bar data for `EURUSD` and `GBPUSD`.
- **Acceptance Criteria:** Student $t$-test $p < 0.01$ on post-Fix mean-reversion returns over 252 trading days.

### RQ-FX-003: VPIN High-Frequency Toxicity as Execution Safeguard
- **Hypothesis:** Pausing order submission when VPIN exceeds $0.75$ reduces 5-minute post-trade market impact and adverse selection by $> 30\%$.
- **Data Required:** Top-of-book tick quotes and trade volumes from TWS / ECN feed handlers.
- **Acceptance Criteria:** Statistically significant reduction in adverse selection ratio ($\text{ASR} < 40\%$).

---

## 3. Review & Qualification Protocol

All research questions must follow the 5-stage research progression:
1. **Hypothesis & Mechanism Formulated:** Formal entry in `RESEARCH_BACKLOG.md`.
2. **Experiment Harness Executed:** Ran on historical datasets with hash verification.
3. **Evidence Bundle Generated:** Artifacts saved to `knowledge/experiments/`.
4. **Independent Replication Passed:** Multi-period and multi-asset replication.
5. **Promotion Gate Ratified:** Approved for deployment in `paper_session.py`.

---

## 4. References & Research Directives

1. **Project TITAN Canonical Research Questions.** [CANONICAL_RESEARCH_QUESTIONS.md](file:///d:/projects/Project%20TITAN/docs/CANONICAL_RESEARCH_QUESTIONS.md).
2. **Project TITAN Research Pipeline.** [promotion.py](file:///d:/projects/Project%20TITAN/src/titan/research/promotion.py).
