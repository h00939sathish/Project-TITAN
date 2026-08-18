# CRYPTO Discovery Report

- **Date:** 2026-08-16
- **ADR-029:** Accepted by Architecture Council / Risk Owner.
- **Status:** All 3 Preregistered Hypotheses Implemented & Tested (Research-Only).

## Summary Scorecard

| Hypothesis | Signal Concept | Ingestion & Manifest | Gate Result | Terminal State |
|---|---|---|---|---|
| **CRYPTO-001** | Funding / Basis Carry | `binance_vision_v1.json` | ❌ OOS Net Sharpe / Replic. Failed | `negative_result` |
| **CRYPTO-002** | Funding + OI Deleveraging | `binance_oi_v1.json` | ❌ OOS Sharpe / Replic. Failed | `negative_result` |
| **CRYPTO-003** | Order-Flow Imbalance (OFI) | `binance_trades_v1.json` | ❌ OOS Capacity / Replic. Failed | `negative_result` |

## Detailed Findings

1. **CRYPTO-001 (Funding / Basis Carry):**
   - Neutralizing directional risk with spot vs perpetual positions is heavily burdened by 10 bps spot taker fees + 5 bps perpetual taker fees.
   - High funding bursts are transient and do not compensate for entry/exit spread and slippage during volatile regime shifts.

2. **CRYPTO-002 (Funding + Open-Interest Deleveraging):**
   - Extreme funding coinciding with open-interest spikes/drops signals market stress, but adverse price momentum and liquidation tails frequently overwhelm mean-reversion entries before the reversal materializes.

3. **CRYPTO-003 (Order-Flow / Liquidity Imbalance):**
   - High-frequency aggressive taker imbalances (OFI) show micro-momentum in-sample, but edge decays within 250ms–500ms under realistic latency and cannot overcome the 5 bps taker fee barrier on centralized venues without VIP/maker rebate status.

## Capital & Execution Boundary
- **Default-Deny Preserved:** No exchange credentials, API keys, broker adapters, paper sessions, `TradeIntent` objects, or execution certificates were issued.
- All three research candidates terminate in absorbing `negative_result` states without parameter snooping or gate relaxation, in full adherence to the Project TITAN Agent Constitution.
