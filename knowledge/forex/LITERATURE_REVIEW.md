# PROJECT TITAN — ACADEMIC LITERATURE REVIEW & EMPIRICAL SYNTHESIS

> **Owner:** Academic Research Analyst & Quantitative Research Division  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Research Foundation & ADR Evidence Corpus  
> **Evidence Taxonomy:** Tier 1 Peer-Reviewed Journals & Tier 2 Policy Research Papers

---

## 1. Executive Synthesis of Academic Literature

Academic research in systematic foreign exchange trading over the past three decades establishes four fundamental empirical facts:

1. **Uncovered Interest Parity (UIP) Failure:** High-yield currencies systematically outperform low-yield currencies on an unhedged basis, validating the persistent positive excess return of the Currency Carry Trade (Fama, 1984; Burnside et al., 2011).
2. **Time-Series Momentum Persistence:** Currency price trends exhibit significant autocorrelation over 1 to 12-month lookback windows, providing "crisis alpha" uncorrelated with traditional equity markets (Moskowitz, Ooi, Pedersen, 2012).
3. **Order Flow Drives Short-Term Returns:** Order flow imbalance (OFI) accounts for over $60\%$ of day-to-day exchange rate variance, proving that microstructure order flow contains fundamental price discovery information (Evans & Lyons, 2002).
4. **Non-Linear Crash Risk:** Carry trade returns are subject to severe negative skewness, requiring dynamic volatility filtering and hard risk gates to prevent tail-risk drawdowns (Menkhoff et al., 2012).

---

## 2. Categorized Literature Taxonomy Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ACADEMIC RESEARCH CLASSIFICATION MATRIX                    │
└─────────────────────────────────────────────────────────────────────────────┘
  Category                Seminal Papers                                Key Finding for TITAN
  ───────────────────────────────────────────────────────────────────────────
  Market Microstructure   Evans & Lyons (2002), Hasbrouck (1991)       Order flow drives exchange rates
  Currency Carry Trade    Fama (1984), Burnside (2011), Menkhoff (2012) UIP fails; carry yields crash risk
  Time-Series Momentum    Moskowitz, Ooi, Pedersen (2012)              Trend persistence across G10 FX
  Execution & Impact      Almgren & Chriss (2000), Biais et al. (2015) Square-root market impact law
  Risk & Tail Events      McNeil et al. (2015), Lopez de Prado (2018)  EVT CVaR outperforms Normal VaR
```

---

## 3. Detailed Literature Breakdown

### 3.1 Uncovered Interest Rate Parity & Carry Trade Evidence
- **Fama, E. F. (1984).** *Forward and spot exchange rates.* Journal of Monetary Economics, 14(3), 319-338.
  - **Finding:** Regression of spot rate changes on forward discount yields a negative coefficient ($\beta < 0$), contradicting UIP.
  - **TITAN Application:** Foundation for yield differential harvesting in `FX-CARRY-VOL`.

- **Menkhoff, L., Sarno, L., Schmeling, M., & Schrimpf, A. (2012).** *Carry trades and global foreign exchange volatility.* Journal of Finance, 67(2), 681-718.
  - **Finding:** High-yield currencies are negatively correlated with global FX volatility; low-yield currencies act as safe havens.
  - **TITAN Application:** Implements VXY volatility index filtering to suspend carry trading during high-volatility regimes.

### 3.2 Time-Series & Cross-Sectional Momentum
  - **TITAN Application:** Conceptually aligns with trend-following dynamics. The active strategy configured in `session_config.json` is `ma-crossover`.


### 3.3 Microstructure & Order Flow Dynamics
- **Evans, M. D., & Lyons, R. K. (2002).** *Order flow and exchange rate dynamics.* Journal of Political Economy, 110(1), 170-180.
  - **Finding:** Interbank order flow explains $63\%$ of daily DM/USD exchange rate changes ($R^2 = 0.63$).
  - **TITAN Application:** Integrates Order Flow Imbalance (OFI) as a short-term predictive feature.

---

## 4. References

1. Full bibliography cataloged in [PAPER_SUMMARIES.md](file:///d:/projects/Project%20TITAN/knowledge/forex/PAPER_SUMMARIES.md).
