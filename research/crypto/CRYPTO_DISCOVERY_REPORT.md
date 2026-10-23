# CRYPTO Discovery Report

- **Date:** 2026-08-16 (failure-mode classification added 2026-08-18; extended 2026-09-22 for CRYPTO-004/005/006)
- **ADR-029:** Accepted by Architecture Council / Risk Owner.
- **Status:** Research program complete through CRYPTO-006. All 6 evaluated hypotheses terminated in absorbing `negative_result` or `probe_gated_rejection` states. CRYPTO-007 (maker-rebate fee-regime feasibility) is in progress under a separate active session — its outcome is not recorded here until sealed by its owner.

## Summary Scorecard

| Hypothesis | Signal Concept | Failure Mode (AGENTS.md Rule 8) | Confidence | Terminal State |
|---|---|---|---|---|
| **CRYPTO-001** | Funding / Basis Carry | **Execution-Constrained Rejection** | High | `negative_result` |
| **CRYPTO-002** | Funding + OI Deleveraging | **Mechanism Failure** | High | `negative_result` |
| **CRYPTO-003** | Order-Flow Imbalance (OFI) | **Execution-Constrained Rejection** | Medium | `negative_result` |
| **CRYPTO-004** | Maker-Oriented Basis & Funding Carry | **Negative Result** (maker leg beat taker baseline; failed net carry hurdle) | High | `negative_result` |
| **CRYPTO-005** | Passive Two-Sided Spread Capture (markout) | **Execution-Constrained Rejection** | High | `probe_gated_rejection` |
| **CRYPTO-006** | Maker Spread Capture, mid-liquidity perp band | **Execution-Constrained Rejection** (measurement-limited qualifier; boundary G2b fail) | High | `probe_gated_rejection` |
| **CRYPTO-007** | Maker-rebate fee-regime feasibility | *In progress — outcome not recorded here* | — | *unsealed* |

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

### CRYPTO-004 — Negative Result (High Confidence)

Maker-oriented basis/funding carry (long spot + short perp, passive post-only maker execution, BTCUSDT/ETHUSDT). Sealed per the canonical evidence record (4,380 real Binance Vision events: 2,190 IS + 2,190 OOS). Maker execution dramatically beat the pure-taker baseline, but the strategy failed the net economic carry hurdle (OOS annualized return / Sharpe / drawdown gates). Mechanism directionally present; harvestable yield insufficient. See `research/crypto/hypotheses/CRYPTO-004-maker-basis-carry.md`.

### CRYPTO-005 — Execution-Constrained Rejection (High Confidence)

Passive two-sided spread capture on BTCUSDT/ETHUSDT USDⓈ-M. IS-month feasibility probe (2024-06 windows, 0.58M–1.79M fills) gave net edge −2.02 to −2.04 bps/fill with block-bootstrap LB95 far below zero. Binding term is the VIP0 2 bps maker fee — roughly **40× the harvestable half-spread (~0.05 bps)**. Markout was slightly favourable, so adverse selection is not the killer; cost is. Rejected at the §1 acquisition gate per the fail-closed proxy rule; OOS never read, 14-month download and shadow phase not run. See `research/crypto/hypotheses/CRYPTO-005-maker-markout.md` §6.

### CRYPTO-006 — Execution-Constrained Rejection, measurement-limited qualifier (High Confidence)

Follow-up on a mid-liquidity perp band (ranks 51–150, 20 symbols by uniform stride, 2025-03-10..16, IS only, OOS never opened). Gate score: G1 PASS (70% of symbols' half-spread clears the fee), G2a PASS (median net +0.157 bps), **G2b FAIL (boundary: 10/20 vs frozen 12/20 threshold)**, G3/G4/G5 PASS. Harvestable spread is ~130× larger than on BTCUSDT (2.39 vs 0.018 bps), confirming CRYPTO-005's fee/spread diagnosis — but `corr(half_spread, net_edge) = 0.967`: the apparent edge sits entirely in the illiquid half where the reversal proxy's overstatement is worst, while every deep name is net negative. Recommending against paid-L2 escalation: depth data would sharpen the already-overstated gross term and move net edge down. Absorbing scope: CRYPTO-006 as registered. See `research/crypto/hypotheses/CRYPTO-006-widespread-maker-capture.md` §10 and `research/crypto/results/CRYPTO-006-probe.json`.

## Capital & Execution Boundary

- **Default-Deny Preserved (through CRYPTO-006):** No exchange credentials, API keys, broker adapters, paper sessions, `TradeIntent` objects, or execution certificates were issued.
- All six evaluated research candidates terminate in absorbing `negative_result` / `probe_gated_rejection` states without parameter snooping or gate relaxation, in full adherence to the Project TITAN Agent Constitution.

## Research Governance

Per ADR-029 and ADR-030, these hypotheses are permanently closed. Reopening crypto research requires a genuinely new, pre-registered hypothesis with a distinct mechanism. Post-hoc parameter sweeping, threshold adjustment, holding-period tuning, or fee-assumption changes on the failed signals are forbidden.
