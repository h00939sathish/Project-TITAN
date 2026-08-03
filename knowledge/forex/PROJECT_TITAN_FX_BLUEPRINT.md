# PROJECT TITAN — MASTER FOREX OPERATING SYSTEM BLUEPRINT

> **Owner:** Architecture Council & Chief FX Quantitative Researcher  
> **Status:** Ratified Master Architecture Blueprint — v1.0  
> **Target System:** Project TITAN FX Autonomous Research & Trading Operating System  
> **Depends On:** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md), [OPERATING_PRINCIPLES.md](file:///d:/projects/Project%20TITAN/OPERATING_PRINCIPLES.md), [FOREX_MARKET_OVERVIEW.md](file:///d:/projects/Project%20TITAN/knowledge/forex/FOREX_MARKET_OVERVIEW.md)

---

## 1. Master System Architecture Diagram

Project TITAN's Forex Operating System integrates high-speed Rust core risk gating, event-driven NautilusTrader execution patterns, Jesse-derived technical indicators, and LLM-assisted research reflection into an un-bypassable deterministic trading loop.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PROJECT TITAN FX OPERATING SYSTEM                     │
└─────────────────────────────────────────────────────────────────────────────┘

 ┌───────────────────────────────────────────────────────────────────────────┐
 │                   1. RESEARCH & ADVISORY LOOP (Python)                    │
 │                                                                           │
 │  ┌─────────────────────┐   ┌─────────────────────┐   ┌──────────────────┐ │
 │  │ LLM Research Agent  │   │ Feature Discovery   │   │ Post-Trade       │ │
 │  │ (Hypothesis Engine) │   │ (TFT / XGBoost)     │   │ Reflection       │ │
 │  └──────────┬──────────┘   └──────────┬──────────┘   └────────┬─────────┘ │
 └─────────────┼─────────────────────────┼───────────────────────┼───────────┘
               │ Proposed Parameters     │ Feature Vectors       │ Insights
               ▼                         ▼                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │                2. QUALIFICATION & REPLICATION GATE (Python)               │
 │                                                                           │
 │  ┌─────────────────────────────────────────────────────────────────────┐  │
 │  │ Qualification Engine (Plateau Stability, Walk-Forward, CPCV)        │  │
 │  └──────────────────────────────────┬──────────────────────────────────┘  │
 └─────────────────────────────────────┼─────────────────────────────────────┘
                                       │ Qualified Strategy Manifests
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │                3. DETERMINISTIC EXECUTION CORE (Rust / PyO3)              │
 │                                                                           │
 │  ┌─────────────────────┐   ┌─────────────────────┐   ┌──────────────────┐ │
 │  │ Rust Risk Gate      │   │ Portfolio Engine    │   │ Reconciliation   │ │
 │  │ (HMAC Risk Tokens)  │   │ (Position / Cash)   │   │ Engine (Drift=0) │ │
 │  └──────────┬──────────┘   └──────────┬──────────┘   └────────┬─────────┘ │
 └─────────────┼─────────────────────────┼───────────────────────┼───────────┘
               │ Signed Approved Order   │ Cash & Margin State   │ Audit Logs
               ▼                         ▼                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │              4. BROKER ADAPTER & REAL-TIME FEED (IBKR TWS)                │
 │                                                                           │
 │  ┌─────────────────────────────────────────────────────────────────────┐  │
 │  │ TWSRealtimeFeed (5-min Intraday Bars) / IBKRPaperAdapter (Port 7497)│  │
 │  └──────────────────────────────────┬──────────────────────────────────┘  │
 └─────────────────────────────────────┼─────────────────────────────────────┘
                                       │ Real-time Quotes & Fills
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │              5. TITAN WEB DASHBOARD & TRADINGVIEW CHARTING                │
 │                                                                           │
 │  ┌─────────────────────────────────────────────────────────────────────┐  │
 │  │ FastAPI Server (Port 8082) + TradingView Lightweight-Charts (OHLCV) │  │
 │  └─────────────────────────────────────────────────────────────────────┘  │
 └───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Platform Adoption & Rejection Decisions

TITAN adopts proven architectural patterns from top quantitative platforms while strictly rejecting god-object shapes and opaque execution loops:

### 2.1 What TITAN Adopts
- **NautilusTrader Architecture:** Event-driven core, strongly typed domain messages, explicit order state machines (`OrderState::Submitted`, `Acknowledged`, `Filled`), and periodic broker reconciliation.
- **Jesse Framework Principles:** Adoption direction per [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md) for indicator concepts (`ma-crossover`, ATR, Bollinger Bands) and parameter optimization methodology.
- **LLM_trader Advisory Reflection:** Post-trade memory, hypothesis scoring, and performance reflection (strictly offline).

### 2.2 What TITAN Rejects
- **Trade Engine (Anti-Pattern Source):** Rejected due to un-gated orders, global state mutation, and silent exception swallowing.
- **Fincept God-Object Shape:** Monolithic single-class design is explicitly prohibited. TITAN mandates decoupled PyO3 Rust components.
- **Direct AI Order Submission:** AI models are constitutionally blocked from submitting or approving orders directly.

---

## 3. Active 10-Symbol FX/Equities Universe & Multi-Asset Sizing

TITAN operates on a unified multi-asset universe configured in [session_config.json](file:///d:/projects/Project%20TITAN/session_config.json):

```json
{
  "mode": "broker-paper",
  "tws": true,
  "dashboard": 8082,
  "instruments": [
    "SPY", "QQQ", "IWM", "EURUSD", "GBPUSD", "XAUUSD", "AAPL", "MSFT", "XLF", "XLK"
  ]
}
```

- **Forex Pair Conventions:**
  - `EURUSD` / `GBPUSD`: Base units = $1,000$ (1 micro-lot per order unit).
  - Short-first USD accumulation dynamics in multi-currency accounts are handled deterministically with zero position drift.

---

## 4. Verification & Governance Summary

Every execution module in TITAN's Forex Operating System is verified through targeted and repository-wide testing:
- **Paper Execution Certification Suite:** 52/52 passing tests (`tests/adapters/` & `tests/certification/`) verifying risk token signing, order fills, reconciliation drift detection, and TWS socket handshakes.
- **Repository Test Suite Baseline:** 707 passed / 13 failed across the entire repository (13 failures located in research/volatility WIP modules under active development).
- **Operational Health:** Verified out-of-the-box zero-argument execution (`python scripts/paper_session.py`).


---

## 5. References & Master Blueprint Specifications

1. **Project TITAN Agent Constitution.** [AGENTS.md](file:///d:/projects/Project%20TITAN/AGENTS.md).
2. **Project TITAN Failure Analysis.** [FAILURE_ANALYSIS.md](file:///d:/projects/Project%20TITAN/FAILURE_ANALYSIS.md).
3. **Project TITAN Adoption Decisions.** [ADOPTION_DECISIONS.md](file:///d:/projects/Project%20TITAN/ADOPTION_DECISIONS.md).
4. **Master Session Config.** [session_config.json](file:///d:/projects/Project%20TITAN/session_config.json).
