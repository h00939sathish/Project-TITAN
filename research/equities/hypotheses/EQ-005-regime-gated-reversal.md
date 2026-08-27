# EQ-005 — US Core-7 Equities Regime-Gated Long-Side Short-Term Reversal Pre-Registration

- **Hypothesis ID:** `EQ-005`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Cost Provenance).
- **Status:** Sealed Pre-Registration (Evaluated on Core-7 Universe).

---

## 1. Economic Hypothesis & Lineage

**Hypothesis:** Short-term cross-sectional mean-reversion alpha is concentrated strictly on the **long side of oversold laggards** when common market conditions exhibit **elevated cross-sectional dispersion**, while the effect weakens or disappears during low-dispersion momentum regimes.

### Derivation from Prior Evidence:
1. **`EQ-001` (12-1M Momentum):** Rejected due to inverted cross-sectional ranking (laggards systematically beat leaders).
2. **`EQ-004` (5-Day Reversal):** Rejected due to broken monotonicity ($\text{Laggards } +30.96\% > \text{Leaders } +21.97\% > \text{Neutral } +19.52\%$) and severe regime fragility (thrived in 2022 bear/high-dispersion market $+22.21\%$, failed in 2023 low-dispersion tech trend $-4.02\%$).
3. **`EQ-005` Mechanism:** Isolates the surviving long leg (Bottom 2 laggards) and gates exposure on market dispersion, completely eliminating the fragile short leg (no shorting of runaway momentum leaders).

---

## 2. Frozen Experimental Parameters

- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT` (Point-in-Time Split & Dividend Adjusted).
- **Signal Formulation:**
  $$S_{i,t} = - \left( \frac{P_{i,t} - P_{i,t-5}}{P_{i,t-5}} \right)$$
  (Ranks lowest 5-day return highest $\implies$ Long Target).
- **Primary Regime Variable (Cross-Sectional Dispersion):**
  $$\text{Dispersion}_t = \frac{1}{21} \sum_{k=0}^{20} \text{std}_{\text{cross-sectional}} \left( R_{i, t-k} \right)$$
  - **Lagged Trigger Rule:** Trade active at $t+1$ if and only if $\text{Dispersion}_{t} > \text{Median}_{\text{IS}}(\text{Dispersion})$.
  - Strictly point-in-time: Uses In-Sample (2020–2022) historical median threshold ($\approx 0.0135$). Zero lookahead.
- **Secondary Diagnostic:** 21-day rolling SPY realized volatility (recorded in evidence bundle for attribution, but does NOT govern trade entries).
- **Portfolio Construction:**
  - **When Regime is Active ($\text{Dispersion}_t > \text{Median}_{\text{IS}}$):** Allocate $+50\%$ to each of the Top 2 laggards ($100\%$ gross long exposure).
  - **When Regime is Inactive ($\text{Dispersion}_t \le \text{Median}_{\text{IS}}$):** Allocate $100\%$ to Cash ($0\%$ equity exposure, $0.0\%$ turnover friction).
- **Rebalance & Holding Rule:** Fixed 5-day holding period (rebalance every 5 trading days, execution at $t+1$ close/open).
- **Partitions:**
  - **In-Sample (IS):** 2020-01-02 to 2022-12-31 (36 months) — defines the frozen dispersion threshold.
  - **Out-of-Sample (OOS):** 2023-01-03 to 2024-12-31 (24 months) — sealed evaluation.
- **Cost Scenarios (Layer 1 Discovery):**
  1. `baseline_alpaca_us_equity`: $\$0.00$ commission, $1.0$ bps spread, $0.5$ bps slippage, $0.04$ bps regulatory fees.
  2. `baseline_ibkr_pro_tiered`: $\$0.0035$/share ($\$0.35$ min), $0.8$ bps spread, $0.3$ bps slippage, $0.04$ bps regulatory fees.
  3. `stressed_adverse`: $\$0.0100$/share ($\$2.00$ min), $3.0$ bps spread, $1.5$ bps slippage, $0.08$ bps regulatory fees.
- **Control Baseline:** Exposure-matched regime-conditioned random selection (randomly selects 2 assets among Core-7 when regime is active, cash when inactive, evaluated across $N=500$ Monte Carlo seeds).

---

## 3. Documented Implementation Caveats from EQ-004

1. **Share-based vs. Dollar Turnover Commission Approximation:** L1 simulator models commissions via $\Delta w \times (\text{commission} / \text{assumed\_price})$ rather than individual executed share counts.
2. **Dollar-Neutral vs. Beta-Neutral:** EQ-004 was dollar-neutral but not strictly beta-neutral. EQ-005 tests long-only excess return vs. cash/random controls to isolate the long-side anomaly directly without short-leg beta contamination.

---

## 4. Decision Gates & Acceptance Criteria

1. **OOS Net Sharpe:** $\ge 0.50$ after L1 baseline costs (Alpaca / IBKR).
2. **Excess Return over Control:** Net Sharpe and annual return statistically exceed the exposure-matched random selection baseline.
3. **Regime Gating Value-Add:** Regime-gated strategy improves Sharpe and maximum drawdown relative to unconditioned 100% long-reversal.
4. **Drawdown Constraint:** OOS Maximum Drawdown $\le 20.0\%$.
5. **Stress Survivability:** Net return remains positive under Adverse Stressed cost schedule.
