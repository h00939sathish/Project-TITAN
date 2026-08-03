# TITAN Canonical Research Questions

> **Status:** Active — Generation 2 (Alpha Discovery Program)  
> **Owner:** Chief Research Architect & Quant Research Team  
> **Last Updated:** 2026-07-30  

---

## Overview
This document registers the core **Canonical Research Questions (RQs)** governing Project TITAN. Unlike one-off experiments or strategy code, these questions represent durable scientific inquiries into market mechanics. Each Canonical Research Question spawns multiple hypotheses, experiments, and replications over time.

---

## Registered Canonical Research Questions

### `RQ-001`: Opening Auction Imbalance Dynamics
* **Question:** How does institutional opening auction imbalance affect first-hour returns and directional intraday drift across equity indices (`SPY`, `QQQ`, `IWM`)?
* **Category:** Market Microstructure
* **Economic Mechanism:** Institutional Market-On-Open (MOO) order flow execution pressure.
* **Target Instruments:** `SPY`, `QQQ`, `IWM`

---

### `RQ-002`: Volatility Compression & Directional Expansion
* **Question:** Under what specific market conditions (ATR percentile, volume contraction, regime) does volatility compression precede clean directional expansion versus false whipsaw breakouts?
* **Category:** Volatility & Regime Dynamics
* **Economic Mechanism:** Liquidity drying prior to institutional positioning and stop-run liquidity sweeps.
* **Target Instruments:** `EURUSD`, `GBPUSD`, `SPY`

---

### `RQ-003`: Execution Microstructure Alpha
* **Question:** How much execution alpha exists through intelligent order placement (midpoint limit orders, TWAP/VWAP execution, dark pool routing) versus naive market order execution?
* **Category:** Execution Research
* **Economic Mechanism:** Bid-ask spread capture and market impact reduction.
* **Target Instruments:** All active paper symbols (`SPY`, `QQQ`, `EURUSD`, `GBPUSD`)

---

### `RQ-004`: Intraday Sector Leadership & Index Lead-Lag
* **Question:** Can intraday sector ETF rotation (`XLF`, `XLK`, `XLE`) reliably predict broad index ETF performance (`SPY`, `QQQ`) with a multi-minute lead time?
* **Category:** Cross-Sectional & Sector Effects
* **Economic Mechanism:** Cross-asset basket arbitrage and institutional portfolio rebalancing lead times.
* **Target Instruments:** `SPY`, `QQQ`, `XLF`, `XLK`

---

### `RQ-005`: Regime-Dependent Momentum Breakdown
* **Question:** Which specific macroeconomic and volatility market regimes (VIX level, yield curve slope, sideways noise) invalidate time-series momentum and trend-following strategies?
* **Category:** Regime Dependence
* **Economic Mechanism:** Mean-reverting noise dominates trend signals in low-volatility / range-bound regimes.
* **Target Instruments:** `EURUSD`, `GBPUSD`, `SPY`, `QQQ`
