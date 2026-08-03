# Forex Broker Execution Specification

> **Owner:** Execution Platform and Risk Owner
> **Status:** Proposed — not approved for IBKR paper or live execution
> **Date:** 2026-07-29
> **Depends on:** `Broker.spec.md`, `Risk.spec.md`, ADR-014, proposed ADR-018

## Purpose

Define the requirements that must be accepted before a TITAN adapter can send a forex order to IBKR. This specification does not authorize an order path.

## Scope and boundary

- In scope after approval: IBKR **paper** execution for EUR/USD, GBP/USD, AUD/USD, and NZD/USD.
- Out of scope: live execution, non-USD-quote pairs, leverage, margin expansion, currency conversion, and account-balances in a non-USD valuation.
- Strategies may emit `TradeProposal`; only `PaperTradingEngine.submit_intent()` may route an approved intent to an adapter.
- The adapter owns IBKR contract translation. IBKR SDK objects must not escape the adapter boundary.

## Canonical contracts

| TITAN ID | IBKR symbol | security type | exchange | currency | quantity rule |
|---|---|---|---|---|---|
| `EURUSD` | `EUR` | `CASH` | `IDEALPRO` | `USD` | multiple of 1,000 base units |
| `GBPUSD` | `GBP` | `CASH` | `IDEALPRO` | `USD` | multiple of 1,000 base units |
| `AUDUSD` | `AUD` | `CASH` | `IDEALPRO` | `USD` | multiple of 1,000 base units |
| `NZDUSD` | `NZD` | `CASH` | `IDEALPRO` | `USD` | multiple of 1,000 base units |

The adapter must resolve and persist the IBKR ConId before routing where available. Position snapshots must map the returned contract back to the same canonical TITAN ID; a bare `symbol` is insufficient.

## State and failure behavior

| Condition | Required behavior |
|---|---|
| FX permission, market data, or contract qualification unavailable | Reject before `placeOrder`; record typed capability failure. |
| Quantity is not an integer multiple of 1,000 | Reject in instrument validation; do not call adapter. |
| Missing broker position or balance snapshot | Trigger kill switch and halt routing. |
| Canonical-ID mapping unavailable | Treat as reconciliation failure; halt routing. |
| Critical reconciliation drift | Trigger kill switch and retain audit evidence. |
| Any request targets a live port | Reject at adapter construction. |

## Monitoring and acceptance evidence

- Metrics: FX contract qualification success/failure, snapshot mapping failures, closed bars, proposals, risk rejections, broker acknowledgements, fills, reconciliation severity, and kill-switch transitions.
- Tests: contract construction and reverse mapping, micro-lot validation, simulated deterministic fills/reconciliation, snapshot failure, critical drift, and paper-port guard.
- Paper-session evidence: recorded successful account permission check, market-data entitlement, contract qualification, reconciliation, and a human-reviewed paper session.

## Rollback

Disable the FX symbols in the session configuration, retain order/reconciliation records, and keep the kill switch engaged. No live route or balance mutation is permitted.

