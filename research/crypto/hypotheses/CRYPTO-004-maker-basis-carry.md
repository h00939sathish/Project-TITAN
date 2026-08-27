# CRYPTO-004: Maker-Oriented Basis & Funding Rate Carry (Pre-Registration)

- **Hypothesis ID:** `CRYPTO-004`
- **Governing ADRs:** ADR-029 (Absorbing Negative Results), ADR-031 (Canonical Simulation Costs).
- **Instruments:** `BTCUSDT`, `ETHUSDT` (Binance Spot + USD-M Perpetual Futures).
- **Status:** Sealed Pre-Registration.

---

## 1. Economic Mechanism & Causal Theory

**Mechanism:** Perpetual futures trade at a structural funding rate premium (contango) relative to the spot index during crypto market expansion. Long Spot $+$ Short Perpetual forms a delta-neutral basis carry position that collects funding cashflow settled every 8 hours (00:00, 08:00, 16:00 UTC).

**Scientific Question:** Can basis and funding carry deliver a durable net economic yield when captured via **passive post-only maker execution**, with explicit modeling of queue priority, fill probability, legging delay, taker hedge fallbacks, and margin liquidation buffers?

---

## 2. Execution Microstructure & Friction Model

```
       Step 1: Signal                  Step 2: Legging Window (≤ 15 min)             Step 3: 8h Settlement
  ┌───────────────────────┐            ┌────────────────────────────────┐            ┌───────────────────┐
  │ Funding Rate > 10% Ann│ ─────────▶ │ 1. Post Perp Maker Sell Limit  │ ─────────▶ │ Earn 8h Funding   │
  │ Basis Spread Normal   │            │ 2. Upon fill, Post Spot Buy    │            │ on Matched Hedged │
  └───────────────────────┘            │    Maker Limit                 │            │ Active Notional   │
                                       │ 3. If Unfilled at 15 min:      │            └───────────────────┘
                                       │    Execute Taker Market Hedge  │
                                       └────────────────────────────────┘
```

1. **Passive Order Routing:**
   * **Perpetual Leg:** Post-only Limit placed at prevailing Best Ask.
   * **Spot Leg:** Post-only Limit placed at prevailing Best Bid immediately upon perpetual fill.
2. **Legging Delay & Taker Fallback Rule:**
   * Maximum allowed maker legging window: $\Delta t_{\max} = 15\text{ minutes}$.
   * If Spot maker order remains unfilled after 15 minutes $\implies$ **Taker Fallback Hedge** (execute Spot at market taker fee $0.05\%$) to eliminate unhedged delta drift.
3. **Captured Funding Cashflow vs. Theoretical Funding:**
   * Funding cashflows are calculated strictly on the *active synchronized hedged notional* in place at the 8-hour settlement timestamps (00:00, 08:00, 16:00 UTC).
4. **Exchange Margin & Liquidation Buffer:**
   * Initial Margin: $20\%$ ($5\times$ maximum leverage on perpetual leg).
   * Maintenance Margin: $10\%$ ($10\times$ liquidation threshold).
   * Liquidation Buffer Gate: Basis widening must never exceed $5.0\%$ of spot price (margin call / de-risking threshold).

---

## 3. Cost Schedule (Layer 1 Discovery / Binance VIP1 Benchmark)

| Cost Component | Spot Leg | Perpetual Leg |
| :--- | :--- | :--- |
| **Maker Fee** | $2.0\text{ bps}$ ($0.02\%$) | $1.0\text{ bps}$ ($0.01\%$) |
| **Taker Fee (Fallback)** | $5.0\text{ bps}$ ($0.05\%$) | $4.0\text{ bps}$ ($0.04\%$) |
| **Slippage Impact** | $0.5\text{ bps}$ | $0.5\text{ bps}$ |
| **Leverage Limit** | $1.0\times$ (Unlevered cash) | $5.0\times$ (Max $20\%$ margin) |

---

## 4. Partitions & Rigorous Control Baselines

- **Partitions:**
  - **In-Sample (IS):** 2024-08-01 to 2025-07-31 (12 months).
  - **Out-of-Sample (OOS):** 2025-08-01 to 2026-07-31 (12 months, sealed).
- **Control Baselines:**
  1. **Frictionless Gross Carry Baseline:** 100% synchronized instantaneous fills with $0.0\%$ fees (measures theoretical gross yield).
  2. **Pure Taker Execution Baseline (CRYPTO-001 Baseline):** Immediate market taker execution on both legs ($10\text{ bps}$ spot $+$ $5\text{ bps}$ perp).
  3. **Random Entry Timing Baseline:** Carry positions entered at randomly assigned dates/times regardless of funding rate magnitude ($N=500$ Monte Carlo).

---

## 5. Acceptance Decision Gates

| Gate | Acceptance Criteria | Failure Action |
|---|---|---|
| **Gate 1: Synchronized Fill Rate** | $\ge 80.0\%$ of entries complete hedging via maker orders without triggering 15-minute taker fallback | Absorbing `negative_result` |
| **Gate 2: Delta-Neutral Integrity** | Mean unhedged directional exposure duration $< 5.0\text{ minutes}$ per rebalance | Absorbing `negative_result` |
| **Gate 3: Maker vs. Taker Superiority** | Maker Net Sharpe exceeds Pure Taker Sharpe by $\ge +0.80$ | Absorbing `negative_result` |
| **Gate 4: Net Economic Carry Hurdle** | OOS Annualized Net Return $\ge +8.0\%$, Net Sharpe $\ge 1.50$, Max Drawdown $\le 5.0\%$ | Absorbing `negative_result` |

If any gate fails, `CRYPTO-004` terminates permanently as an absorbing `negative_result` without post-hoc fee tweaking.
