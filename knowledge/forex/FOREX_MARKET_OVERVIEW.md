# PROJECT TITAN — FOREX MARKET OVERVIEW & ECOSYSTEM ARCHITECTURE

> **Owner:** Quantitative FX Division & Macroeconomic Council  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Forex Research Operating System  
> **Evidence Priority:** Tier 1 Academic (Journal of Finance, JFE, JIMF) & Tier 2 Policy (BIS, Fed, ECB, CME, CLS)

---

## 1. Global FX Market Structure & Cash Flow Dynamics

The Foreign Exchange (FX) market is the largest, most liquid financial market in the world, with daily turnover exceeding **$7.5 trillion** (BIS Triennial Central Bank Survey, 2022). Unlike centralized exchange-traded equity markets (e.g., NYSE, NASDAQ), FX operates as a global, decentralized, over-the-counter (OTC) multi-tiered network.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 1: INTERBANK LIQUIDITY MATRIX                       │
│    Tier 1 Money-Center Banks (JPMorgan, Citi, UBS, Deutsche Bank, HSBC)    │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
             ┌─────────┴─────────┐           ┌─────────┴─────────┐
             │ EBS Market (Spot) │           │ Refinitiv Matching│
             └─────────┬─────────┘           └─────────┬─────────┘
                       │                               │
┌──────────────────────▼───────────────────────────────▼──────────────────────┐
│                    TIER 2: NON-BANK LIQUIDITY & ECNS                        │
│    Non-Bank Market Makers (XTX Markets, Citadel Securities, Jump, Virtu)   │
│    Electronic Communication Networks (Currenex, FastMatch, Cboe FX, LMAX)  │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
             ┌─────────┴─────────┐           ┌─────────┴─────────┐
             │  Prime Brokerage  │           │   Direct API /    │
             │   (PB Access)     │           │   FIX Engines     │
             └─────────┬─────────┘           └─────────┬─────────┘
                       │                               │
┌──────────────────────▼───────────────────────────────▼──────────────────────┐
│                    TIER 3: SYSTEMATIC INSTITUTIONAL TRADERS                 │
│        Project TITAN Execution Core, Quant Funds, Corporate Treasuries     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Capital Flow Mechanics Across Tiers
1. **Tier 1 Interbank Market:** Top money-center dealers (JPMorgan, Citi, UBS, Deutsche Bank) quote continuous bilateral bid-ask prices. Trades clear through **CLS Bank (Continuous Linked Settlement)** to eliminate Payment-versus-Payment (PvP) Herstatt settlement risk.
2. **Tier 2 Non-Bank Market Makers & ECNs:** Algorithmic liquidity providers (XTX Markets, Citadel Securities) operate automated market-making algorithms on Electronic Communication Networks (ECNs) such as EBS Market, Refinitiv Matching, Cboe FX, and LMAX Exchange.
3. **Tier 3 Institutional Access (TITAN Layer):** TITAN accesses FX liquidity via Credit Prime Brokers (e.g., Interactive Brokers, Saxo, or Institutional PB accounts). Orders are routed via FIX protocol (Financial Information eXchange v4.2/v4.4) or PyO3 Rust execution bindings with sub-millisecond deterministic risk gating.

---

## 2. FX Market Participants & Structural Roles

| Participant Class | Structural Incentive | Time Horizon | Order Flow Characteristics | Market Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Central Banks & Sovereign Wealth** | Policy intervention, reserve management, interest rate targeting | Months to Years | Large, persistent, unconstrained by short-term PnL | High long-term structural regime shift |
| **Corporates & Trade Commercials** | Currency hedging, cross-border M&A, supply chain settlement | Weeks to Months | Inelastic demand, calendar/month-end fixing flows | Moderate, predictable fixing concentration (e.g., 4 PM London Fix) |
| **Macro Hedge Funds & CTA Systems** | Absolute return, trend capture, carry harvest, yield extraction | Days to Months | Directional, momentum-aligned, leverage-utilizing | Moderate-to-high medium-term trend reinforcement |
| **High-Frequency Traders (HFT)** | Spread capture, latency arbitrage, order flow toxicity detection | Microseconds to Seconds | High-frequency, ultra-short holding periods, order cancellation heavy | Sub-second bid-ask spread compression |
| **Non-Bank Market Makers** | Two-way liquidity provision, inventory risk optimization | Seconds to Minutes | Mean-reverting inventory management, skew adjustment | Compressed spreads, sudden liquidity withdrawal during tail events |
| **Retail Speculators & Brokers** | Leverage speculation, retail flow aggregated by B-Book brokers | Minutes to Days | High churn, adverse selection prone, retail sentiment indicator | Low market impact; serves as counterparty flow for institutional liquidity |

---

## 3. FX Instrument Architecture & Settlement Conventions

### 3.1 Spot Forex (`secType="CASH"`, `secType="FOREX"`)
- **Settlement Cycle:** $T+2$ business days for most G10 pairs; $T+1$ for USD/CAD and USD/TRY.
- **Convention:** Base currency / Quote currency (e.g., `EURUSD`: Base = EUR, Quote = USD).
- **Lot Sizing Standardization:**
  - **Standard Lot:** 100,000 base currency units ($1.0$ lot).
  - **Mini Lot:** 10,000 base currency units ($0.1$ lot).
  - **Micro Lot:** 1,000 base currency units ($0.01$ lot / `STEP_SIZE=1000` in TITAN).
  - *TITAN Convention:* In [forex_pairs.py](file:///d:/projects/Project%20TITAN/src/titan/data/forex_pairs.py#L38-L40), 1 unit = 1 micro-lot (1,000 base currency units). A BUY order of `quantity=1000` on `EURUSD` represents €1,000 notional ($\approx \$1,090$ USD at 1.09 EUR/USD).

### 3.2 FX Swaps & Forward Outrights
- **FX Forward:** Agreement to buy/sell a currency pair at a specified future date at a forward exchange rate reflecting the Covered Interest Rate Parity (CIP) differential:
  \[
  F = S \times \frac{1 + r_{\text{quote}} \times \frac{d}{360}}{1 + r_{\text{base}} \times \frac{d}{360}}
  \]
- **FX Swap:** Simultaneous purchase of spot currency and sell of forward currency (or vice versa). Accounted for in overnight rollover / swap points (Tom-Next points).

### 3.3 Currency Futures & Options
- Exchange-traded contracts cleared via CME (Chicago Mercantile Exchange) Globex (e.g., 6E for EUR/USD, 6B for GBP/USD, 6J for JPY/USD).
- Fully centralized order book matching engine with transparent Level 2 / Level 3 Market Depth (DOM).

---

## 4. Multi-Currency Portfolio Sizing & Margin Realities

### 4.1 Base Currency Settlement Reality (INR / USD / EUR Accounts)
In multi-currency portfolios, PnL is realized in the **quote currency** of the pair, while account balances are maintained in the account **base settlement currency**.

```
Order Intent: EURUSD BUY 1000 units (€1,000 Notional)
  ├── Required Initial Margin: €1,000 / Leverage (e.g. 50:1 = €20)
  ├── Required Buying Power: Notional Value in USD ≈ $1,090 USD
  ├── Cash Balance Safeguard: If USD cash < $1,090 → IBKR TWS Error 201 (Insufficient Buying Power)
  └── Short-Sale Asymmetry: SELL EURUSD 1000 units generates USD cash proceeds immediately,
      enabling short-first capital accumulation in USD-deficient multi-currency accounts.
```

### 4.2 Deterministic Risk & Reconciliation Safeguards
TITAN enforces deterministic boundaries for multi-currency handling:
1. **Unsafe Currency Rejection:** USD-quote pairs only (`EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`). Non-USD quote pairs (USD/JPY, USD/CHF) require multi-currency portfolio conversion and are rejected at the data layer per [forex_pairs.py](file:///d:/projects/Project%20TITAN/src/titan/data/forex_pairs.py#L3-L6).
2. **Reconciliation Drift Immunity:** If a broker rejects an order due to buying power constraints (Error 201), TITAN's PyO3 Rust risk gate records a clean `OrderState::Rejected` transition, preventing position drift and keeping local portfolio state 100% in sync with broker truth (`drift = 0`).

---

## 5. References & Academic Evidence

1. **BIS Triennial Survey (2022).** *OTC foreign exchange turnover in April 2022.* Bank for International Settlements.
2. **Lyons, R. K. (2001).** *The Microstructure Approach to Exchange Rates.* MIT Press.
3. **Rime, D., & Schrimpf, A. (2013).** *The technological transformation of the FX market.* BIS Quarterly Review.
4. **Evans, M. D., & Lyons, R. K. (2002).** Order flow and exchange rate dynamics. *Journal of Political Economy*, 110(1), 170-180.
5. **Project TITAN Architecture Constitution.** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md).
