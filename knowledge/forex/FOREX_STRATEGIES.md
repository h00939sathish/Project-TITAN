# PROJECT TITAN — SYSTEMATIC FOREX STRATEGY TAXONOMY & REGIME SPECTRUM

> **Owner:** Systematic FX Strategy Lead & Quantitative Research Division  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Strategy Pool & Signal Generators  
> **Evidence Priority:** Tier 1 Academic (Journal of Finance, JFE, Review of Financial Studies) & Tier 2 Benchmark Evidence

---

## 1. Systematic Strategy Taxonomy & Matrix

Systematic FX strategies are categorized by primary anomaly source, holding period, market regime suitability, and transaction cost sensitivity.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROJECT TITAN FOREX STRATEGY MATRIX                      │
└─────────────────────────────────────────────────────────────────────────────┘
  Strategy Family            Primary Driver          Holding Period   Regime
  ───────────────────────────────────────────────────────────────────────────
  1. G10/EM Carry Trade      Yield Differential      Days to Months   Low Volatility / Risk-On
  2. Time-Series Momentum    Trend Persistence       Days to Weeks    Trending / High Volatility
  3. Cross-Sectional Mom.    Relative Strength       Days to Weeks    Divergent Macro Trends
  4. Mean-Reversion / Range   Oversold/Overbought     Hours to Days    Ranging / Low Volatility
  5. Volatility Breakout     Band Compression        Hours to Days    Transition (Low → High Vol)
  6. StatArb / Pairs        Cointegration Spread    Hours to Days    Co-integrated Pairs
  7. Order Flow Imbalance    Microstructure Toxicity Minutes to Hours High-Frequency Order Flow
```

---

## 2. Deep Dive into Major FX Strategy Families

### 2.1 Currency Carry Trade (Unhedged & Volatility-Adjusted)
- **Theory & Mechanism:** Exploits the failure of Uncovered Interest Rate Parity (UIP). High-interest-rate currencies do not depreciate fast enough to offset interest rate differentials, creating a positive net yield harvest:
  \[
  R_{\text{carry}, t+1} = \frac{S_{t+1} - S_t}{S_t} + \left( r_{\text{quote}, t} - r_{\text{base}, t} \right)
  \]
- **Empirical Evidence (Burnside et al., 2011; Menkhoff et al., 2012):** Carry yields an unadjusted Sharpe ratio of $0.60 - 0.85$ over multi-decade horizons, but suffers severe **crash risk** (negative skewness) during global liquidity crises (e.g., 2008 GFC, March 2020 pandemic).
- **TITAN Status:** ⏳ Backlog Specification (`RQ-FX-001`). Presumes central bank rate-differential feeds (OIS / swap points) that are not yet ingested in `src/titan/data`. Position sizing logic will scale inversely to 30-day realized volatility once yield differential feeds are active.

### 2.2 Time-Series Momentum (TSMOM) & Trend Following
- **Theory & Mechanism:** Captures slow adjustment of exchange rates to economic fundamentals, central bank monetary policy shifts, and institutional flow persistence (Moskowitz, Ooi, Pedersen, 2012):
  \[
  \text{Signal}_t = \text{sign} \left( R_{t-L, t} \right) \times \frac{\sigma_{\text{target}}}{\sigma_t}
  \]
- **Empirical Evidence:** TSMOM exhibits positive skewness ("crisis alpha"), generating strong returns during major currency trends (e.g., USD multi-year bull runs, JPY rapid devaluations).
- **TITAN Status ([session_config.json](file:///d:/projects/Project%20TITAN/session_config.json#L3-L7)):** ✅ Active Strategy (`ma-crossover`). Executes moving average crossover trend signals on 5-min intraday and daily bar feeds.


### 2.3 Cross-Sectional Momentum (CSMOM)
- **Theory & Mechanism:** Ranks currencies across the G10 universe based on relative performance over a trailing 1 to 12-month period, longing top-tier performers and shorting bottom-tier underperformers:
  \[
  z_i = \frac{R_i - \mu_R}{\sigma_R}
  \]
- **Empirical Evidence:** Provides zero-net-exposure dollar-neutral returns with low correlation to directional equity or bond markets.

### 2.4 Statistical Arbitrage & Cointegration Pairs Trading
- **Theory & Mechanism:** Identifies long-term stationary relationships between economically linked currency pairs (e.g., `EURUSD` vs `GBPUSD`, or `AUDUSD` vs `NZDUSD`).
- **Engle-Granger Cointegration Test:**
  \[
  \text{EURUSD}_t = \alpha + \beta \cdot \text{GBPUSD}_t + \epsilon_t
  \]
- **Trading Signal:** Standardized spread $z_t = \frac{\epsilon_t - \mu_\epsilon}{\sigma_\epsilon}$. Trade when $|z_t| > 2.0$, exiting at $z_t = 0.0$.

---

## 3. Strategy Strengths, Failure Modes & Transaction Cost Sensitivity

| Strategy Family | Sharpe Ratio Range | Max Drawdown | Failure Modes & Risk Vulnerability | Transaction Cost Sensitivity |
| :--- | :--- | :--- | :--- | :--- |
| **Carry Trade** | $0.60 - 0.85$ | $-35\%$ to $-55\%$ | Rapid risk-off unwinding, liquidity freeze, central bank intervention | Low (Holding period: weeks-months) |
| **Time-Series Momentum** | $0.50 - 0.75$ | $-15\%$ to $-25\%$ | Prolonged choppiness, sudden trend reversals | Moderate (Holding period: days-weeks) |
| **Cross-Sectional Mom.** | $0.60 - 0.90$ | $-12\%$ to $-20\%$ | Macro regime shifts, monetary policy convergence | Moderate (Holding period: days-weeks) |
| **Mean-Reversion** | $0.70 - 1.10$ | $-20\%$ to $-35\%$ | Strong structural breakout, persistent trend | High (Holding period: hours-days) |
| **Order Flow Imbalance** | $1.20 - 2.50$ | $-5\%$ to $-10\%$ | Latency disadvantage, broker execution rejections | Critical (Holding period: minutes-hours) |

---

## 4. References & Academic Strategy Evidence

1. **Burnside, C., Eichenbaum, M., Kleshchelski, I., & Rebelo, S. (2011).** Do currency carry trades have positive betas? *Journal of Finance*, 66(2), 667-688.
2. **Menkhoff, L., Sarno, L., Schmeling, M., & Schrimpf, A. (2012).** Carry trades and global foreign exchange volatility. *Journal of Finance*, 67(2), 681-718.
3. **Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012).** Time series momentum. *Journal of Financial Economics*, 104(2), 228-250.
4. **Lustig, H., Roussanov, N., & Verdelhan, A. (2011).** Common risk factors in currency markets. *The Review of Financial Studies*, 24(11), 3731-3777.
5. **Project TITAN Strategy Runner Implementation.** [paper_session.py](file:///d:/projects/Project%20TITAN/scripts/paper_session.py#L95-L125).
