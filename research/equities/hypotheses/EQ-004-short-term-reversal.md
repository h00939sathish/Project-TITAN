# EQ-004 — US Core-7 Equities 5-Day Cross-Sectional Short-Term Reversal Pre-Registration

- **Hypothesis ID:** `EQ-004`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-030 (Factor Simulation), ADR-031 (Canonical Simulation Costs).
- **Status:** Sealed Pre-Registration (Evaluated on Core-7 Universe).

---

## 1. Economic Mechanism & Hypothesis

**Hypothesis:** Short-horizon price shocks induce temporary cross-sectional dislocations and liquidity imbalances across liquid equity instruments that partially mean-revert as market makers provide liquidity and order flow normalizes.

**Independent Theoretical Basis:** Unlike long-term momentum (which relies on underreaction over 3–12 months) or long-term value/reversal (which relies on fundamental multi-year overreaction), 1-week short-term reversal is driven by short-term inventory imbalances and temporary liquidity demand spikes. This test stands strictly on its own economic rationale and is not an inverted continuation of `EQ-001`.

---

## 2. Frozen Experimental Parameters

- **Universe ($N=7$):** `SPY`, `QQQ`, `IWM`, `XLF`, `XLK`, `AAPL`, `MSFT` (Identical Point-in-Time Split & Dividend Adjusted series as `EQ-001`).
- **Signal Formulation:**
  $$S_{i,t} = - \left( \frac{P_{i,t} - P_{i,t-5}}{P_{i,t-5}} \right), \quad z_{i,t} = \frac{S_{i,t} - \mu_t}{\sigma_t}$$
  (Ranks lowest 5-day return highest $\implies$ Long Target; highest 5-day return lowest $\implies$ Short Target).
- **Portfolio Construction:**
  - Dollar-neutral: Top 2 Long ($+25\%$ each $\implies +50\%$), Bottom 2 Short ($-25\%$ each $\implies -50\%$), Middle 3 Neutral ($0\%$).
  - Net Exposure: $0.0$.
  - Gross Exposure: $1.0$ ($100\%$).
- **Rebalance Frequency:** 5 trading days (weekly cadence).
- **Execution Timing:** Decision at $t$, execution at $t+1$ (strictly causal, zero lookahead).
- **Partitions:**
  - **In-Sample (IS):** 2020-01-02 to 2022-12-31 (36 months).
  - **Out-of-Sample (OOS):** 2023-01-03 to 2024-12-31 (24 months).
- **Cost Scenarios (Layer 1 Discovery):**
  1. `baseline_alpaca_us_equity`: $\$0.00$ commission, $1.0$ bps spread, $0.5$ bps slippage, $50$ bps borrow, $0.04$ bps regulatory fees.
  2. `baseline_ibkr_pro_tiered`: $\$0.0035$/share ($\$0.35$ min), $0.8$ bps spread, $0.3$ bps slippage, $50$ bps borrow, $0.04$ bps regulatory fees.
  3. `stressed_adverse`: $\$0.0100$/share ($\$2.00$ min), $3.0$ bps spread, $1.5$ bps slippage, $150$ bps borrow, $0.08$ bps regulatory fees.
- **Control Baseline:** Exposure-matched random-ranking portfolio with identical universe, turnover mechanics, rebalance dates, and holding periods (evaluated over $N=1000$ bootstrap iterations and fixed-seed baseline).

---

## 3. Decision Gates & Outcome Categorization

| Case | Category | Criteria | Consequence |
|---|---|---|---|
| **Case A** | **Strong Predictive Alpha** | OOS Net Sharpe $> 0$, Mean Rank IC $> 0$, Monotonicity Verified, Survives Both Venues + Stress | Qualifies for Layer 2 Historical Calibration. |
| **Case B** | **Execution-Constrained Rejection** | Gross OOS $> 0$, Net OOS $< 0$ under realistic friction | Absorbing `negative_result` (Document friction drag). |
| **Case C** | **Overfit / Regime-Fragile** | IS Net Sharpe $> 0$, OOS Net Sharpe $< 0$ | Absorbing `negative_result`. |
| **Case D** | **Mechanism Failure** | Mean Rank IC $\le 0$ or no distinct information vs. random control | Absorbing `negative_result`. |
| **Case E** | **Inverted Signal** | Strong negative IC | Absorbing `negative_result` (No post-hoc inversion allowed). |
