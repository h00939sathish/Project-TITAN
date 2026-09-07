# EQ-Micro-001 — ETF Constituent Intraday Lead-Lag & Basket Imbalance Pre-Registration

- **Hypothesis ID:** `EQ-Micro-001`
- **Factor Name:** `etf_constituent_intraday_lead_lag`
- **Asset Class:** US Liquid Equities & ETFs (5-Minute Intraday)
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Sealed Pre-Registration (Full 2020–2024 Multi-Regime Coverage)

---

## 1. Economic Hypothesis & Rationale

### The Mechanism:
1. **Intraday Information Diffusion & Index Arbitrage Lag:**
   - Benchmark ETFs (`SPY`, `QQQ`, `XLK`, `XLF`) trade with the deepest liquidity in global equities, rapidly discounting macro and systematic news into prices.
   - Individual single-stock constituents exhibit heterogeneous reaction times due to order queue dynamics, fragmented retail/institutional flow, and inventory management by market makers.
   - When an index or sector ETF experiences an intraday return impulse exceeding normal volatility ($|\Delta r_{\text{ETF}}| > 1.5\sigma$), basket arbitrageurs transmit this flow to constituent stocks.
   - Laggard constituents (those whose trailing return is significantly below the implied basket impulse) reliably drift toward the ETF basket return over the subsequent 15 to 60 minutes.

2. **Independence from Fundamental Estimates (Pure Market Data):**
   - Unlike `EQ-007`/`EQ-008` (which depend on point-in-time consensus earnings surprises), `EQ-Micro-001` operates exclusively on **pure market data** (intraday prices, volume, and cross-sectional ETF basket tracking).
   - It requires zero third-party analyst estimate feeds or fundamental data vendor access.

3. **Intraday Risk Containment & Overnight Neutrality:**
   - All positions are entered conditionally on intraday impulses, managed with a fixed holding deadband (30–60 minutes), and **strictly liquidated to 100% cash by 15:55 ET (flat-at-close)**.
   - Eliminates overnight gap risk, earnings release shock risk outside market hours, and short borrow financing fees.

4. **Friction Avoidance (Lessons from `EQ-002`):**
   - `EQ-002` failed because 414%/month turnover generated -2.64%/yr friction drag.
   - `EQ-Micro-001` guards against over-trading by requiring:
     1. Impulse trigger gating (only trading when ETF impulse $|r| > 1.5\sigma$).
     2. A 30-minute minimum holding deadband to prevent tick-by-tick churn.
     3. An explicit **Friction Drag Ratio Gate** ($\le 45\%$ of gross alpha consumed by transaction costs).

---

## 2. Frozen Experimental Parameters

- **Universe:** 
  - Manifest: `research/equities/manifests/us_sp50_liquid_intraday_v1.json`
  - ETF Anchors: `SPY`, `QQQ`, `XLK`, `XLF`
  - Equities: 50 Liquid US Large-Cap Equities
- **Signal Formulation:**
  - **Trailing ETF Basket Impulse:**
    $$I_{\text{ETF}, t} = \frac{r_{\text{ETF}, [t-3, t]}}{\sigma_{\text{ETF}, 20\text{d}}}$$
  - **Constituent Residual Return:**
    $$\epsilon_{i, t} = r_{i, [t-3, t]} - \beta_i \cdot r_{\text{ETF}, [t-3, t]}$$
  - **Cross-Sectional Lead-Lag Alpha Score:**
    $$S_i(t) = -\text{rank}(\epsilon_{i, t}) \times \mathbb{I}(|I_{\text{ETF}, t}| > 1.5)$$
- **Portfolio Construction:**
  - Dollar-Neutral (Long Top Quintile, Short Bottom Quintile).
  - Target Gross Exposure: $1.0\times$ ($50\%$ Long, $50\%$ Short).
  - Holding Window: 30 to 60 minutes (6 to 12 5m bars).
  - Mandatory Flat at 15:55 ET (zero overnight exposure).
- **Partitions (Full Multi-Regime 2020–2024 Parity):**
  - **In-Sample (IS):** 2020-01-02 to 2022-12-31 (36 months, includes 2020 COVID shock & 2022 bear market).
  - **Out-of-Sample (OOS):** 2023-01-03 to 2024-12-31 (24 months strict holdout).
- **Cost Model (ADR-031 Canonical Simulation):**
  - Commission: $\$0.005$ / share with IBKR $\$1.00$ minimum per order.
  - Half-spread: $1.0$ bps.
  - Market impact / Slippage: $0.5$ bps.
  - Overnight borrow: $\$0.00$ (strictly intraday flat).

---

## 3. Decision Gates & Acceptance Criteria

| Gate | Metric | Hurdle | Rationale |
|---|---|---|---|
| **Gate 1** | OOS Net Sharpe | $\ge 1.20$ | Annualized net Sharpe under full $\$1.00$ min commission schedule |
| **Gate 2** | Rank IC Positive Fraction | $\ge 65\%$ | Cross-sectional predictive stability across intraday periods |
| **Gate 3** | Mean Rank IC | $\ge 0.03$ | Statistically significant lead-lag predictive ranking power |
| **Gate 4** | Quantile Monotonicity | Top > Mid > Bottom | Ordered returns across sorted quintiles |
| **Gate 5** | Max Intraday Drawdown | $\le 6.0\%$ | Downside risk containment with zero overnight carry |
| **Gate 6** | Friction Drag Ratio | $\le 45\%$ | $\frac{\text{Total Friction}}{\text{Gross PnL}} \le 0.45$ (guards against EQ-002 churn failure) |
| **Gate 7** | Stressed Adverse Net Return | $> 0.0$ | Positive net PnL under doubled spread ($2.0$ bps) & $\$2.00$ fee minima |
