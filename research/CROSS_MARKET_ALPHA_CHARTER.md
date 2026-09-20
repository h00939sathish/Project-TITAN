# Cross-Market Alpha Research Charter

- **Status:** Proposed — Research-only; governed by ADR-033
- **Date:** 2026-08-28
- **Owners:** Research Platform, Architecture Council, Risk Owner
- **Scope:** Cross-instrument information transmission, scheduled macroeconomic surprise transmission, and structural relative-value response; strictly no live capital authority.

---

## 1. Objective & Operational Invariants

The objective of this charter is to define the exact empirical evaluation protocols, data contracts, and quantitative decision gates for **Cross-Market Alpha** discovery in Project TITAN, ensuring research integrity and preventing premature infrastructure development.

### Invariants:
1. **Zero Execution Authority:** All research is strictly offline and read-only. No live capital, credentials, order paths, broker adapters, or paper trading instances may be spawned.
2. **Absorbing Exclusion Registry:** Previous terminal findings on single-pair liquid OHLCV (FX, Equities, Crypto) cannot be retuned, relaxed, or reopened.
3. **Data Before Code:** Verified point-in-time (PIT) data contracts and checksummed manifests must exist before writing hypothesis evaluation code.

---

## 2. Hypothesis Exclusion Registry

The following signal families and mechanisms are permanently classified as **absorbing negative results** and are strictly excluded from cross-market research:

| Excluded Family | Historical Reference | Reason for Permanent Exclusion |
| :--- | :--- | :--- |
| **Liquid FX Intraday Momentum** | `EXP-00016`, `EXP-00022` | Spread friction exceeds gross mechanism return across all major/minor pairs. |
| **FX Carry / Vol-Carry** | `EXP-00023`, `EXP-00024` | Tail risk asymmetry and structural unwinds destroy risk-adjusted returns. |
| **Crypto Perp Directional OHLCV** | `CRYPTO-001`..`003` | Liquidation cascades and noise mining yield 0 net OOS persistence. |
| **Unhedged Single-Asset Mean Reversion** | `EXP-00020`, `EXP-00026` | Regime shifts produce unbounded drawdown without cointegrated structural anchor. |
| **Bar-Close Constant-bps Simulations** | `ADR-0005`, `ADR-0031` | Fails to account for quote-side fills, queue position, and latency slippage. |

---

## 3. Data Contracts & Point-in-Time Specifications

Any dataset utilized in cross-market research must satisfy the following contract specifications:

1. **Provider & Licensing:** Documented primary source (e.g., direct exchange feed, institutional macro calendar provider, official statistical bureau).
2. **Point-in-Time Availability:** Every observation must carry an exact UTC release timestamp (`available_at_utc`) separate from the economic event timestamp (`event_timestamp_utc`) to guarantee zero lookahead bias.
3. **Revision Tracking:** Vintage tracking for economic indicators (e.g., initial print vs. first revision vs. benchmark revision).
4. **Price Synchronization:** High-resolution executable quote data (top-of-book bid/ask with size) synchronized across all evaluated instruments to millisecond precision.
5. **Storage & Manifest:** Frozen in `research/cross_market/manifests/` with SHA-256 integrity hashes.

---

## 4. Priority Candidate Hypothesis: `CM-001`

### `CM-001`: Scheduled Macroeconomic Surprise Transmission

- **Economic Mechanism:**
  Scheduled macroeconomic releases (US Non-Farm Payrolls, CPI, PPI, FOMC Decisions) create quantifiable information shocks relative to consensus expectations. Different liquid asset classes (Equities: SPY/QQQ, Fixed Income: TLT/IEF, Financials: XLF) adjust to interest rate and inflation surprises at varying speeds due to participant composition and liquidity depth.
- **Hypothesis:**
  A dollar-neutral relative-value dislocation occurs between interest-rate sensitive assets and equity beta during the post-release adjustment window (T+1s to T+15m), providing net alpha after aggressive taker execution fees.
- **Falsifying Counter-Mechanism:**
  Algorithmic market makers in liquid US ETFs update cross-asset quotes synchronously within $< 5\text{ms}$ of headline release, eliminating exploitable price divergence and leaving only spread crossing costs.
- **Admitted Universe:**
  Liquid US ETFs: `SPY`, `QQQ`, `IWM`, `TLT`, `IEF`, `XLF`, `XLE`.
- **Decision Horizon:**
  Event-driven entry at `T+release`, holding period 5 minutes to 60 minutes with hard time-stop.

---

## 5. Cost & Friction Attribution Model

Every cross-market backtest must explicitly attribute PnL components in its canonical evidence bundle:

$$\text{PnL}_{\text{net}} = \text{PnL}_{\text{gross}} - \text{Cost}_{\text{spread}} - \text{Cost}_{\text{comm}} - \text{Cost}_{\text{borrow}} - \text{Cost}_{\text{latency}} - \text{Cost}_{\text{impact}}$$

1. **Spread Drag:** Half-spread on entry and exit based on historical prevailing quote-side prices at execution timestamp.
2. **Broker Commissions:** Standard institutional tier ($0.0035/share or 0.5 bps).
3. **Short Borrowing Costs:** 50 bps annualized cost on short legs, accrued per second held.
4. **Data Latency Delay:** Mandatory simulated execution delay (e.g., 50ms, 100ms, 250ms) to model real-world API processing and order queue placement.
5. **Hedging / Legging Risk:** Explicit attribution of tracking error if long and short legs fill asynchronously.

---

## 6. Frozen Quantitative Decision Gates

To pass Phase 1 admission and qualify for a shadow-observation proposal, hypothesis `CM-001` must satisfy all 5 gates simultaneously on the Out-of-Sample (OOS) partition:

| Gate | Metric | Pass Threshold | Falsification Consequence |
| :--- | :--- | :--- | :--- |
| **Gate 1** | **Annualized Net Sharpe** | $\ge 1.20$ (net of all friction) | Immediate `mechanism_failure` |
| **Gate 2** | **Profit Factor** | $\ge 1.40$ on OOS | Immediate `mechanism_failure` |
| **Gate 3** | **Information Coefficient** | Mean IC $\ge 0.06$, Positive in $\ge 65\%$ of release events | Immediate `mechanism_failure` |
| **Gate 4** | **Latency Sensitivity** | Net Sharpe remains $\ge 0.80$ under 200ms latency penalty | Classified as `execution_constrained_rejection` |
| **Gate 5** | **Max Drawdown** | $\le 10.0\%$ during OOS evaluation period | Immediate `mechanism_failure` |

---

## 7. Terminal Outcome Protocol

1. **Failure (Absorbing):**
   - If any gate fails on OOS data, write an absorbing negative result record to `research/cross_market/neg_results/CM-001_terminal.md`.
   - The hypothesis ID `CM-001` is permanently locked. Re-running with modified parameters is prohibited.
2. **Success (Shadow Candidate Only):**
   - If all gates pass, assemble the canonical simulation evidence bundle and submit an **ADR Proposal for Shadow Monitoring** to the Architecture Council.
   - Live trading and paper trading remain unauthorized without formal council ratification.
