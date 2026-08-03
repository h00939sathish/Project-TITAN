# PROJECT TITAN — FX DATA HIERARCHY, INGESTION & QUALITY ASSURANCE

> **Owner:** Data Engineering Lead & Quantitative Research Division  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Data Ingestion Core & Feed Handlers  
> **Data Integrity Directive:** Zero look-ahead bias, zero synthetic leakage without hash verification.

---

## 1. FX Data Hierarchy & Quality Matrix

Institutional FX trading requires a multi-layered data ingestion strategy spanning tick-level microstructure, intraday OHLCV bars, macroeconomic indicators, and cross-asset yield curves.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROJECT TITAN FX DATA HIERARCHY                        │
└─────────────────────────────────────────────────────────────────────────────┘
  Layer                   Update Frequency  Latency Target   Use Case
  ───────────────────────────────────────────────────────────────────────────
  1. Realtime Tick / L2   Tick-by-tick      < 10 ms          Execution / OFI / Slippage Model
  2. Intraday OHLCV       5-min / 15-min    Real-time (RTH)  Strategy Signal Generation
  3. Swap Points & Forward Daily            End-of-Day       Carry Calculation / Rollover
  4. OIS Yield Curves     Daily            End-of-Day       Central Bank Parity Modeling
  5. CFTC COT Reports     Weekly           Friday 3:30 PM   Institutional Positioning Bias
  6. Macro Releases (NFP) Event-driven     Real-time        Event-Volatility Circuit Breaker
```

---

## 2. Detailed Data Source Evaluation

### 2.1 Real-Time & Historical Market Data

| Data Source | Type | Asset Coverage | Latency / Quality | Cost Profile | TITAN Integration |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Interactive Brokers (TWS / API)** | Tick / 5-min OHLCV / Top-of-Book | Full G10 + EM FX Pairs | Real-time streaming (< 100 ms) | Low (Included with active paper/live account) | **Primary Live Feed** via `TWSRealtimeFeed` & `TWSDataFeed` |
| **Alpaca Market Data API** | Intraday OHLCV | Equities & Selected FX | REST / WebSocket API (< 200 ms) | Free Tier / Low | Primary fallback for US Equities & Paper preflight |
| **EBS Market / Refinitiv Matching** | Tick / Level 3 Depth | Spot G10 FX | Sub-millisecond ECN feed | High Institutional ($$$$) | Target enterprise ECN connector |
| **CME Futures Data (6E, 6B, 6J)** | L2 / L3 Order Book | FX Futures | Direct Exchange Feed (< 5 ms) | Moderate | Futures Volume & Order Flow Imbalance (OFI) proxy |

### 2.2 Macroeconomic & Fundamental Data

1. **CFTC Commitments of Traders (COT) Reports:**
   - **Metrics:** Non-Commercial Long vs Short Positions, Commercial Hedger Positions.
   - **Frequency:** Published every Friday at 3:30 PM ET (reflecting Tuesday position data).
   - **Signal Application:** Extremes in Non-Commercial net positioning ($> 2.0$ std dev from 52-week mean) signal crowded carry or momentum trades prone to rapid unwinds.
2. **OIS Yield Curves & Central Bank Swap Rates:**
   - Overnight Index Swaps (SOFR, ESTR, SONIA, TONA) provide market-implied central bank rate hike/cut probabilities.
   - Used in `FX-CARRY-VOL` to dynamically forecast 30-day forward yield differentials.

---

## 3. Data Integrity & Validation Pipeline

TITAN enforces a 5-point automated verification pipeline on all incoming market data before passing bars to strategy generators:

```
Incoming Feed ──► [1. Hash Verification] ──► [2. Duplicate Timestamp Check]
                                                     │
                                                     ▼
                  [5. RTH Window Filter]  ◄── [4. Outlier Spike Filter] ◄── [3. Zero-Volume Audit]
```

1. **Hash Verification:** All historical dataset files carry SHA-256 integrity hashes stored in date manifests (`manifest.json`).
2. **Duplicate & Ordering Enforcement:** Timestamp series must be strictly ascending and unique ($t_i > t_{i-1}$).
3. **Outlier Spike Filter:** Bars where $|p_t - p_{t-1}| > 5 \times \text{ATR}_{14}$ are flagged as bad ticks and quarantined.
4. **Timezone Normalization:** All timestamps are normalized to **UTC ISO-8601** (`YYYY-MM-DDTHH:MM:SSZ`) at ingestion.

---

## 4. References & Data Specifications

1. **CFTC Commitments of Traders Documentation.** U.S. Commodity Futures Trading Commission.
2. **Interactive Brokers API Reference.** *TWS API Documentation — Historical and Realtime Bar Sizes.*
3. **Project TITAN Data Pipeline.** [forex_pairs.py](file:///d:/projects/Project%20TITAN/src/titan/data/forex_pairs.py) and [tws_feed.py](file:///d:/projects/Project%20TITAN/src/titan/data/tws_feed.py).
