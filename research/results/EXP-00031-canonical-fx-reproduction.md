# EXP-00031: Canonical FX Simulation Reproduction Report

- **Experiment ID:** `EXP-00031`
- **Timestamp:** 2026-08-16T15:09:26.847915+00:00
- **Governance Authority:** ADR-031 (Ratified), ADR-028 (Default Deny)
- **Strategy Candidate:** `TraderDevEMA9VWAP` (EXP-00025 candidate)
- **Status:** **RESEARCH EVIDENCE ONLY — NOT ELIGIBLE FOR PROMOTION**

## 1. Executive Summary

This experiment reruns the EXP-00025 TraderDev EMA9×VWAP strategy under the canonical, cost-aware simulator defined in ADR-031.
Crucially, the canonical simulator incorporates:
1. **Both-leg fee schedules:** Assessing the IBKR Tier-1 $2.00 minimum on entry AND exit fills.
2. **Next-event quote-sided execution:** Fills at bar *t+1* open ask (for buys) and open bid (for sells).
3. **Canonical sizing:** Exact lot sizing parity (`Sizer`) with integer step size constraints.
4. **Deterministic provenance hashing:** Cryptographic digests linking dataset, parameters, sizing, and cost model.

## 2. Configuration & Provenance Digests

| Component | Specification / Parameter | SHA-256 Digest |
|---|---|---|
| **Parameters** | `ema=9, vwap=120, atr=14, trail=3.0` | `e8ba9b6e26f90fdb93dc0695c14f05418366699b51ba90cc5187261cc4898a6d` |
| **Sizing** | `alloc=10.0%, step=1000, min=1000` | `f1af5093ee5a5738dda376615358911776ebb1686ab8b59292e84bfbc66cedb7` |
| **Cost Model** | `IBKR Tier-1 ($2 min, 0.20bps, sided quotes)` | `961ecdfc2a9cba79a223e13b6e40ab09fb72d32e2341220ae510f427d10fb64d` |
| **EURUSD Data** | `Dukascopy 1m Bid/Ask resampled to 4h` | `7d194a5778be9a3ba764371a2a784b55bbd7a4a56c2b41dc12c94a860aff9135` |
| **GBPUSD Data** | `Dukascopy 1m Bid/Ask resampled to 4h` | `159ca77d98477de4fef8ef844fb8c04dd2287dcb515f113dc1a6c01e8d1ee07b` |

## 3. Reproduction Performance & Cost Attribution Matrix

### EURUSD (4-Hour Bars)
- **In-Sample Partition:** 2025-08-01T00:00:00Z to 2026-03-09T20:00:00Z (966 bars)
- **Out-of-Sample Partition:** 2026-03-10T00:00:00Z to 2026-07-31T20:00:00Z (644 bars)

| Metric | In-Sample (IS) | Out-of-Sample (OOS) |
|---|---|---|
| Total Return (%) | -0.01% | +0.01% |
| Sharpe Ratio | -0.01 | 0.03 |
| Max Drawdown (%) | 0.37% | 0.27% |
| Win Rate (%) | 58.8% | 18.2% |
| Profit Factor | 3.41 | 0.78 |
| Total Trades | 17 | 11 |
| Total Commission ($) | $34.00 | $22.00 |
| Total Slippage Cost ($) | $1.59 | $1.02 |
| Gross PnL ($) | $415.48 | $-56.98 |
| Net PnL ($) | $381.48 | $-78.98 |

### GBPUSD (4-Hour Bars)
- **In-Sample Partition:** 2025-08-01T00:00:00Z to 2026-03-09T20:00:00Z (966 bars)
- **Out-of-Sample Partition:** 2026-03-10T00:00:00Z to 2026-07-31T20:00:00Z (644 bars)

| Metric | In-Sample (IS) | Out-of-Sample (OOS) |
|---|---|---|
| Total Return (%) | +0.23% | +0.20% |
| Sharpe Ratio | 0.34 | 0.66 |
| Max Drawdown (%) | 0.28% | 0.10% |
| Win Rate (%) | 46.1% | 61.5% |
| Profit Factor | 5.29 | 6.19 |
| Total Trades | 13 | 13 |
| Total Commission ($) | $26.00 | $26.00 |
| Total Slippage Cost ($) | $1.23 | $1.22 |
| Gross PnL ($) | $673.42 | $279.75 |
| Net PnL ($) | $647.42 | $253.75 |

## 4. Key Findings & Cost Reality

1. **Ticket Minima Impact:** The $2.00 per-fill ticket minimum significantly degrades micro-lot and small notional trading. On a 10,000 USD position, a round-trip fee of $4.00 represents 4.0 bps of cost (rather than the unhedged 0.4 bps nominal rate).
2. **Zero-Order Governance Authority:** In accordance with ADR-028 and ADR-031, this evidence does not qualify the strategy for execution or promotion. No promotion certificate is issued.

## 5. Promotion Verdict

> [!IMPORTANT]
> **Verdict: NOT ELIGIBLE FOR PROMOTION**
> - OOS Sharpe and return profiles fail the mandatory multi-pair consistency hurdle under canonical costs.
> - Strategy registration remains research-only. Paper and live execution remain strictly denied under ADR-028 default-deny policy.