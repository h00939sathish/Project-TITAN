# CRYPTO Discovery Report

- **Date:** 2026-08-16 (failure-mode classification added 2026-08-18)
- **ADR-029:** Accepted by Architecture Council / Risk Owner.
- **Status:** Research program complete. All 3 preregistered hypotheses terminated in absorbing `negative_result` states.

## Summary Scorecard

| Hypothesis | Signal Concept | Failure Mode (AGENTS.md Rule 8) | Confidence | Terminal State |
|---|---|---|---|---|
| **CRYPTO-001** | Funding / Basis Carry | **Execution-Constrained Rejection** | High | `negative_result` |
| **CRYPTO-002** | Funding + OI Deleveraging | **Mechanism Failure** | High | `negative_result` |
| **CRYPTO-003** | Order-Flow Imbalance (OFI) | **Execution-Constrained Rejection** | Medium | `negative_result` |

## Failure-Mode Classification

Per AGENTS.md Rule 8, each negative result is classified as either *Mechanism Failure* (the underlying theory has no predictive alpha or is directionally inverted) or *Execution-Constrained Rejection* (gross economic transfer exists but friction exceeds harvestable yield under the tested execution model). These classifications describe the tested implementations and execution assumptions, not universal claims about crypto markets.

### CRYPTO-001 — Execution-Constrained Rejection (High Confidence)

The funding/basis carry mechanism generated **positive net PnL** in both IS and OOS partitions ($482 net after fees, spread, and impact). The mechanism produced a gross funding transfer, but VIP0 taker economics (10 bps spot taker + 5 bps perpetual taker) made it unharvestable at scale. The hypothesis failed only the replication gate — independent period/venue replication could not be established.

This does not establish that funding carry is universally unprofitable; it establishes that the tested taker execution path at Binance VIP0 fee tiers consumed more than the transfer produced at the required replication standard.

### CRYPTO-002 — Mechanism Failure (High Confidence)

The funding + OI deleveraging signal fired 6 trades in-sample, all of which lost money (net −$990; fees alone: $825). The OOS partition produced **zero trades** — the extreme funding + OI co-occurrence conditions did not materialize. The hypothesized reversal mechanism did not survive even when it actually triggered: adverse price momentum and liquidation tails overwhelmed mean-reversion entries before reversal materialized.

Execution cost was not the sole or primary failure mode. The mechanism itself lacked predictive power in the tested formulation.

### CRYPTO-003 — Execution-Constrained Rejection (Medium Confidence)

The OFI screen processed 37 IS events and 3 OOS events but executed **zero trades** across all partitions. The latency-decay filter built into the screen blocked execution because the modeled OFI edge decayed within 250ms–500ms under realistic execution latency and could not clear the 5 bps taker fee barrier without VIP/maker rebate status.

**Disambiguation:** The evidence bundle alone does not prove whether OFI threshold crossings occurred and were then filtered by latency decay, or whether thresholds were never breached. The classification is `execution_constrained` based on the screen's latency-decay mechanism design, not on observed profitable-then-eroded trades. This remaining ambiguity is why confidence is `medium` rather than `high`. The classification does not establish that order-flow information is nonexistent in crypto markets; it establishes that the tested latency/fee environment could not monetize it.

## Capital & Execution Boundary

- **Default-Deny Preserved:** No exchange credentials, API keys, broker adapters, paper sessions, `TradeIntent` objects, or execution certificates were issued.
- All three research candidates terminate in absorbing `negative_result` states without parameter snooping or gate relaxation, in full adherence to the Project TITAN Agent Constitution.

## Research Governance

Per ADR-029 and ADR-030, these hypotheses are permanently closed. Reopening crypto research requires a genuinely new, pre-registered hypothesis (e.g. `CRYPTO-004`) with a distinct mechanism. Post-hoc parameter sweeping, threshold adjustment, holding-period tuning, or fee-assumption changes on the failed signals are forbidden.
