# Project TITAN — Profit-Engine-AI (v2.0) Architecture & Milestone Plan

## Architecture Overview

Profit-Engine-AI (v2.0) is an autonomous multi-agent quantitative trading system on Project TITAN that combines a high-performance deterministic execution core in Rust (`core/`, PyO3 `titan._core`) with an institutional-grade Python strategy, research, simulation, and risk management plane (`src/titan/`).

```
                    ┌────────────────────────────────────────────────────────┐
                    │               Profit-Engine-AI (v2.0)                  │
                    │               Autonomous Governance                    │
                    └──────────────────────────┬─────────────────────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
┌──────────────────────────────┐                              ┌──────────────────────────────┐
│     Research & Data Plane    │                              │     Execution & Risk Plane   │
│  - PIT Ingestion & Manifests │                              │  - Default-Deny Ingress Gate │
│  - Pre-registered Hypotheses │                              │  - Ed25519 Cert Verification │
│  - ADR-029/030 Absorbing Neg │                              │  - Deterministic Risk Engine │
│  - ADR-031 Canonical Costs   │                              │  - SHA-256 HMAC Risk Tokens  │
│  - Top-of-Book Quote Fills   │                              │  - IBKR TWS Port 7497 Ingress│
│  - Multi-Asset Simulators    │                              │  - SQLite Event Sourcing     │
└──────────────┬───────────────┘                              └──────────────▲───────────────┘
               │                                                             │
               └───────────── Promotion Gate (8 Fail-Closed Checks) ─────────┘
```

---

## Feature Inventory

Every feature discovered in the Survey Phase is inventoried below and mapped to its governing Milestone:

| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|--------|
| 1 | Ground-Truth Code & DB Audit | Audit of `src/titan`, `core/`, `.titan_state.db`, `titan_research.db`, test suites | M1 | Survey 1 & 2 | **VERIFIED** |
| 2 | Strategy Failure Mode Classification | Categorize ~40 hypotheses into Mechanism Failure vs Execution-Constrained Rejection | M1 | Survey 1 | **VERIFIED** |
| 3 | Execution Ingress & Risk Wiring Audit | Audit Default-Deny, Ed25519 cert verification, HMAC tokens, TWS 7497 bracket orders | M1 | Survey 1 & 2 | **VERIFIED** |
| 4 | Point-in-Time Data Ingestion & Normalization | Ingestion pipeline with symbol validation, price envelopes, canonical UTC timestamps | M2 | Survey 3 | **VERIFIED** |
| 5 | SHA-256 Cryptographic Data Manifests | File chunk hashing (8192 bytes) and deterministic `DataManifest` / `FactorManifest` | M2 | Survey 3 | **VERIFIED** |
| 6 | Market Data Quarantine & Gap Detection | Normalization error isolation, business-day and intraday gap checking, delisted survivorship | M2 | Survey 3 | **VERIFIED** |
| 7 | Multi-Market Trading Calendars | NYSE/NASDAQ, Forex, Spot Metals, 24/7 Crypto market calendars and session logic | M2 | Survey 3 | **VERIFIED** |
| 8 | Point-in-Time Corporate Actions Engine | Split and dividend backward adjustment engine (`CorporateActionsDB`) without look-ahead | M2 | Survey 3 | **VERIFIED** |
| 9 | Feed Health & Watermark Freshness Gate | Fail-closed feed monitor checking watermark advancement, disconnect storms, freshness | M2 | Survey 3 | **VERIFIED** |
| 10 | Structured Hypothesis Pre-Registration | Formal pre-registration schemas (`hypotheses/*.json`) with frozen IS/OOS partitions | M3 | Survey 2 & 3 | **VERIFIED** |
| 11 | Absorbing Negative Results Chronicle | Permanent transition to absorbing `negative_result` records (ADR-029/ADR-030) | M3 | Survey 1 & 2 | **VERIFIED** |
| 12 | 3D Replication Framework | Validation across Instrument, Time Period, and Regime dimensions | M3 | Survey 2 | **VERIFIED** |
| 13 | Mechanism Registry & MEI Index | Quantitative mechanism scoring (MEI 0.00-1.00) across 5 weighted dimensions | M3 | Survey 2 | **VERIFIED** |
| 14 | Multi-Asset Hypothesis Pipeline | Pipeline for Equities Factor (`EQ-004`), FX Microstructure, Crypto Basis, Spot Metals | M3 | Survey 3 | **VERIFIED** |
| 15 | Canonical FX Cost Model (`FxCostModel`) | ADR-031 model: 0.20 bps fee, **$2.00 IBKR ticket minimum**, 0.10 bps spread/slippage | M4 | Survey 3 | **VERIFIED** |
| 16 | Institutional Equities Cost Model (`FactorCostModel`) | ADR-030 model: $0.005/sh fee, 1 bps spread, 0.5 bps slippage, 50 bps annual short borrow | M4 | Survey 3 | **VERIFIED** |
| 17 | Institutional Crypto Cost Model (`CryptoCostModel`) | ADR-029 model: VIP0 taker/maker fees, 1 bps spread, slippage, funding cashflows | M4 | Survey 3 | **VERIFIED** |
| 18 | Quote-Sided Top-of-Book Fill Simulator | `QUOTE_NEXT_EVENT` fill engine on bar $t+1$ with lot step rounding (`Sizer`) | M4 | Survey 3 | **VERIFIED** |
| 19 | Cross-Sectional Factor Simulator | Dollar-neutral quantile spread simulation with lagged weights, turnover drag, and IC | M4 | Survey 3 | **VERIFIED** |
| 20 | Institutional Metrics Suite & Bootstrap CI | Sharpe, Sortino, Calmar, MaxDD, Win Rate, Profit Factor, CAGR, Block Bootstrap 95% CI | M4 | Survey 3 | **VERIFIED** |
| 21 | Default-Deny Execution Engine | Reject uncertified intents, isolate shadow signals, fail-closed order lifecycle | M5 | Survey 1 & 2 | **VERIFIED** |
| 22 | Cryptographic Promotion Certificate Gate | Verify unexpired Ed25519 certificates, parameter binds, dataset digests, dual signers | M5 | Survey 1 & 2 | **VERIFIED** |
| 23 | Deterministic Risk Pipeline & HMAC Signing | 9-stage risk veto pipeline attaching SHA-256 HMAC tokens to `ApprovedOrderIntent` | M5 | Survey 1 & 2 | **VERIFIED** |
| 24 | IBKR TWS Port 7497 Paper Adapter | Paper execution adapter with automatic Stop-Loss, Take-Profit, and Trailing brackets | M5 | Survey 1 & 2 | **VERIFIED** |
| 25 | SQLite Event Store State Persistence | Append-only event store (`.titan_state.db`) for order state transitions and recovery | M5 | Survey 1 | **VERIFIED** |
| 26 | Fail-Closed Session Initialization | Dual-human authorized session startup (`initialize_new_session`) with bounded TTL | M5 | Survey 2 | **VERIFIED** |
| 27 | Staged Capital Scaling Governance | Staged deployment gates: Stage 1 ($10k paper) -> Stage 2 ($25k staged) -> Stage 3 ($100k live) | M6 | Survey 2 | **VERIFIED** |
| 28 | Dual-Human Kill Switch Release Authorization | `ReleaseAuthorization` nonces with dual-signature verification and feed health check | M6 | Survey 2 | **VERIFIED** |
| 29 | Continuous Learning & Advisory Reflection | Post-trade reflection memory without autonomous capital modification authority | M6 | Survey 2 | **VERIFIED** |
| 30 | E2E Opaque-Box Acceptance Verification | Comprehensive 4-tier E2E verification across all target subsystems and market assets | Final | Survey 1-3 | **VERIFIED** |

---

## Milestones

| # | Name | Scope & Deliverables | Dependencies | Status |
|---|------|----------------------|-------------|--------|
| **M1** | **Ground-Truth Code & Database Audit** | Audit `src/titan`, `core/`, `.titan_state.db`, `titan_research.db`, catalog ~40 hypotheses into Mechanism Failure vs Execution-Constrained Rejection, verify Default-Deny execution invariants. | None | **DONE** |
| **M2** | **Point-in-Time Data Ingestion & Quality Pipeline** | Ingestion pipeline with SHA-256 manifests (`DataManifest`, `FactorManifest`), quality quarantine, business-day & intraday gap checks, multi-market trading calendars, point-in-time corporate actions (`CorporateActionsDB`), and feed health gates. | M1 | **DONE** |
| **M3** | **Strategy Development & Hypothesis Pre-Registration** | Formal hypothesis pre-registration schemas (`hypotheses/*.json`), absorbing negative results chronicle (ADR-029/030), 3D replication matrix, Mechanism Registry (MEI), and multi-asset candidate pipeline (`EQ-004`, FX, Crypto, Metals). | M1, M2 | **DONE** |
| **M4** | **Canonical Cost-Aware Simulation Engine** | Institutional simulation suite: `FxCostModel` (ADR-031 $2.00 min fee), `FactorCostModel` (short borrow + per-share commissions), `CryptoCostModel` (funding cashflow), quote-sided top-of-book fills, dollar-neutral factor simulator, and 95% Bootstrap CI metrics engine. | M2, M3 | **DONE** |
| **M5** | **Deterministic Risk Gates & Paper Ingress** | End-to-end paper trading ingress: Default-Deny execution engine, authentic Ed25519 `PromotionCertificateRegistry` verification, 9-stage deterministic `RiskGate`, SHA-256 HMAC intent signing, IBKR TWS port 7497 bracket adapter, and `.titan_state.db` SQLite event sourcing. | M4 | **DONE** |
| **M6** | **Staged Deployment & Live Governance** | Staged capital scaling governance (Stage 1-3), dual-human `ReleaseAuthorization` nonces, feed health release gates, and post-trade reflection advisory logging. | M5 | **DONE** |
| **Final** | **E2E Acceptance & Adversarial Hardening** | 100% pass of 4-tier E2E test suite (Tiers 1-4) + 44 adversarial simulation stress tests + 16 cryptographic forensic probes (Total 1,037 tests passing). | M1-M6, E2E Track | **DONE** |

---

## Interface Contracts

### 1. Data Pipeline ↔ Simulation Engine (`src/titan/data` ↔ `src/titan/backtest`)
- **Type**: `ApprovedDataSource`, `DataManifest`, `MarketEvent`, `EquitiesUniverseData`
- **Contract**:
  - `load_approved(path, ...)` returns verified records with matching SHA-256 checksum and freshness $\le 2$ trading days.
  - `DataManifest.compute_digest()` produces a deterministic 64-character hex string binding raw data, date bounds, and adjustments.
  - `CorporateActionsDB.adjust_bars(bars)` produces backward-adjusted OHLCV price envelope and adjusted volume without forward leakage.

### 2. Strategy & Research ↔ Simulation Engine (`src/titan/strategies` ↔ `src/titan/research` ↔ `src/titan/backtest`)
- **Type**: `StrategyRunner`, `Sizer`, `CostModel`, `BacktestResult`, `FactorSimulationResult`
- **Contract**:
  - Signal evaluation at bar $t$ executes strictly at bar $t+1$ against `QUOTE_NEXT_EVENT` bid/ask top-of-book prices.
  - Sizer applies instrument lot step (`Instrument.lot_step`) and tick size quantization.
  - All cost models must implement deterministic `digest()` and return total friction breakdown (`commission_usd`, `spread_usd`, `slippage_usd`, `borrow_usd`, `funding_usd`).
  - Pre-registered hypotheses failing OOS gates must record permanent absorbing negative result entry.

### 3. Strategy / Promotion ↔ Execution Ingress (`src/titan/research` ↔ `src/titan/execution`)
- **Type**: `TradeIntent`, `PromotionCertificate`, `ApprovedOrderIntent`, `RiskDecision`
- **Contract**:
  - `TradeIntent` must include valid `certificate_ref` (serialized JSON or SHA-256 digest of signed `PromotionCertificate`).
  - `PromotionCertificateRegistry.verify(cert)` verifies genuine Ed25519 digital signature against trusted public key, non-expired validity, and manifest digest match.
  - Shadow intents (`producer_kind == "shadow"`) are strictly blocked at execution ingress with `ValueError`.

### 4. Execution Engine ↔ Deterministic Risk Core (`src/titan/execution` ↔ `core/src/risk.rs`)
- **Type**: `RiskGate`, `RiskConfig`, `ApprovedOrderIntent`, `RiskVerdict`
- **Contract**:
  - `RiskGate.evaluate_intent(intent, portfolio, risk_state)` evaluates 9 sequential checks: schema, certificate, strategy eligibility, data freshness, order limits, position exposure, portfolio drawdown, liquidity/impact, and broker health.
  - `ApprovedOrderIntent.attach_risk_token(secret_key)` generates SHA-256 HMAC token.
  - Broker adapter verifies token before submitting to broker; missing/invalid token causes fail-closed rejection.

### 5. Broker Adapter ↔ Exchange / TWS Gateway (`src/titan/execution/ibkr_adapter.py` ↔ IBKR TWS)
- **Type**: `IBKRPaperAdapter`, `TWSDataFeed`
- **Contract**:
  - Locked to paper ports (`7497`, `8874`) and paper account IDs (`DU*`, `DF*`, `PAPER*`).
  - Emits bracket orders containing Parent Order + Child Stop-Loss + Child Take-Profit + Child Trailing Stop.
  - Disconnection triggers immediate kill switch `TradingState::Halted`.
