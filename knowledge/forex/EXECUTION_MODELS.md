# PROJECT TITAN — FOREX EXECUTION ALGORITHMS & TRANSACTION COST ANALYSIS (TCA)

> **Owner:** Institutional Execution Specialist & Algorithmic Trading Lead  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Execution Engine & TWAP Slicer  
> **Execution Directive:** Sub-millisecond risk verification, zero un-sliced large market order routing.

---

## 1. Institutional FX Execution Infrastructure & SOR

Executing foreign exchange trades across fragmented OTC liquidity venues requires specialized execution algorithms to minimize market impact, adverse selection, and slippage.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TITAN SMART ORDER ROUTING (SOR) ENGINE                   │
└─────────────────────────────────────────────────────────────────────────────┘
  Strategy Order Intent (Approved by Rust Risk Gate with HMAC Token)
    │
    ▼
  [Order Sizer & TWAP Slicer] ──► (If Q > 50 Micro-Lots, Split into N Slices)
    │
    ▼
  [Smart Order Router (SOR)]
    ├── ECN Liquidity Check (EBS vs Refinitiv vs LMAX Top-of-Book)
    ├── Latency & Toxicity Scoring (Avoid Venues with High Adverse Selection)
    └── Broker Order Placement (IBKR FIX / PyO3 Adapter)
```

---

## 2. Execution Algorithm Taxonomies

### 2.1 Time-Weighted Average Price (TWAP)
- **Objective:** Slices a large parent order $Q$ into equal child order slices $q_i = \frac{Q}{N}$ executed at uniform time intervals $\Delta t = \frac{T}{N}$.
- **TITAN Implementation ([twap.py](file:///d:/projects/Project%20TITAN/src/titan/execution/twap.py)):** Triggers automatically when order quantity exceeds 50 micro-lots (`qty > 50`), slicing the order into child orders executed over a configurable duration window.

### 2.2 Volume-Weighted Average Price (VWAP)
- **Objective:** Dynamically matches the intra-day volume profile of the currency pair:
  \[
  q_t = Q \cdot \frac{V_t}{\sum_{k=1}^N V_k}
  \]
- **Application:** Used during high-volume sessions (London/New York overlap, 8:00 AM – 11:00 AM ET) to minimize market impact.

### 2.3 Implementation Shortfall (IS) / Arrival Price Algorithms
- **Objective:** Minimizes total execution cost defined as the difference between the final execution price and the benchmark arrival mid-price $P_0$:
  \[
  \text{IS} = \sum_{i=1}^N q_i (P_i - P_0) + \text{Fees}
  \]
- **Trade-off:** Balances execution risk (holding risk of unexecuted shares) against market impact risk.

---

## 3. Transaction Cost Analysis (TCA) & Metrics

TITAN evaluates every executed order using 4 quantitative TCA metrics:

| TCA Metric | Formula | Target Benchmark |
| :--- | :--- | :--- |
| **Slippage vs Arrival Price** | $\text{Slippage} = \frac{P_{\text{fill}} - P_{\text{arrival}}}{P_{\text{arrival}}} \times 10,000 \text{ pips}$ | $< 0.3 \text{ pips for G10 Spot}$ |
| **Implementation Shortfall** | $\text{IS} = S \cdot \left( P_{\text{fill}} - P_{\text{mid}} \right) + \text{Commissions}$ | $< 0.5 \text{ pips equivalent}$ |
| **Market Impact (5-min Post-Fill)** | $\text{MI}_5 = \frac{P_{t+5m} - P_{\text{fill}}}{P_{\text{fill}}}$ | Stable (Zero directional leak) |
| **Adverse Selection Ratio** | $\text{ASR} = \frac{\mathbf{1}_{\{P_{t+1m} \text{ moves against fill}\}}}{\text{Total Fills}}$ | $< 45\%$ |

---

## 4. References & Execution Specifications

1. **Almgren, R., Thum, C., Hauptmann, E., & Li, H. (2005).** Direct estimation of equity market impact. *Risk*, 18(7), 57-62.
2. **Biais, B., Foucault, T., & Rochet, J. C. (2015).** Microstructure of financial markets. *Econometrica*.
3. **Project TITAN TWAP Executor.** [twap.py](file:///d:/projects/Project%20TITAN/src/titan/execution/twap.py).
4. **IBKR Broker Adapter Implementation.** [ibkr_adapter.py](file:///d:/projects/Project%20TITAN/src/titan/execution/ibkr_adapter.py).
