# ADR-032: Authorize Non-Custodial Read-Only Shadow Paper Deployment for CRYPTO-004 Maker Carry

- **Status:** Accepted (2026-09-01) — Architecture Council and Risk Owner
- **Date:** 2026-09-01
- **Owners:** Research Platform, Architecture Council, Risk Owner
- **Decision scope:** Shadow paper simulation, live market event ingestion, and evidence generation for CRYPTO-004 (BTCUSDT, ETHUSDT)
- **Supersedes / superseded by:** Extends ADR-029 and ADR-031; complements ADR-028; authorizes NO live capital or broker execution

---

## Context

Empirical exploration under ADR-029 demonstrated that taker fee friction severely constrains high-turnover directional crypto strategies (e.g. CRYPTO-001..003). Pre-registration `CRYPTO-004` formulates a passive, maker-oriented basis and funding rate carry mechanism on `BTCUSDT` and `ETHUSDT` perpetual futures and spot pairs, modeled under Binance VIP1 fee schedules.

To observe continuous market behavior, evaluate live queue fill probabilities, track unhedged legging duration, and compute mark-to-market basis PnL in a production-like market stream without exposing capital to risk, Project TITAN requires a dedicated non-custodial shadow pipeline.

---

## Decision

1. **Non-Custodial Read-Only Shadow Authority:**
   - Authorize the implementation and deployment of `CryptoShadowRunner` in `src/titan/research/crypto_shadow_runner.py`.
   - The shadow runner operates exclusively on streaming and historical `CryptoMarketEvent` records (funding, quotes, trades, book snapshots).

2. **Strict Default-Deny Security Boundary:**
   - **Zero Broker Credentials:** No exchange API keys, secrets, or passphrase configs are permitted in shadow configuration or memory.
   - **Zero Capital Authority:** The shadow runner cannot place orders, route intents, modify margin accounts, or interact with paper/live exchange execution engines.
   - **Zero Certificate Self-Issuance:** Shadow execution cannot self-issue a `PromotionCertificate` or alter `PromotionGate` logic.

3. **Strict Execution Import Ban:**
   - Modules in the crypto research/shadow pipeline (`src/titan/research/crypto_shadow_runner.py`) are strictly prohibited from importing any module from `titan.execution`, `titan.runtime`, or external broker adapters.
   - Source-level import bans are enforced via automated regression tests (`assert_research_only_source`).

4. **High-Fidelity Microstructure & Cost Tracking:**
   - The shadow runner consumes incoming market events to maintain a simulated mark-to-market virtual book across `BTCUSDT` and `ETHUSDT`.
   - Simulates post-only maker queue fills and 15-minute legging timeout fallbacks.
   - Accrues funding payments strictly on *matched hedged active notional* at 8-hour settlement intervals (00:00, 08:00, 16:00 UTC).
   - Evaluates full friction attribution under the Binance VIP1 fee schedule (2.0 bps spot maker, 1.0 bps perp maker, 5.0 bps spot taker fallback, 4.0 bps perp taker fallback, 1.0 bps spread, 0.5 bps slippage).

5. **Observable Evidence Export:**
   - Exposes `get_shadow_status()` for live telemetry (positions, mark prices, unrealized basis PnL, cumulative net PnL, fill rates, unhedged duration).
   - Exposes `export_shadow_evidence()` to serialize canonical evidence bundles for governance review.

---

## Alternatives and Trade-offs

- **Direct Paper Trading via Exchange API:** Rejected. Connecting live API keys to an unpromoted research strategy violates ADR-028 default-deny invariants and introduces venue security and counterparty risk.
- **Static Backtest-Only Evaluation:** Rejected. Offline backtests cannot capture real-time order-book queue queue dynamics, latency degradation, and dynamic spread widening across live continuous feeds.
- **Exploratory Bar-Close Constant-BPS Estimation:** Disqualified under ADR-031. High-fidelity top-of-book and quote-sided attribution is mandatory for shadow observation.

---

## Consequences

- **Positive:** Enables real-time verification of CRYPTO-004 maker fill rates, legging timeouts, basis volatility, and funding cashflow without capital exposure.
- **Negative:** Requires running independent shadow ingestion processes; cannot execute real liquidity orders to test physical queue priority directly on the live matching engine.

---

## Implementation Gate & Validation

1. **Specification & ADR:** Ratified in ADR-032 and `research/crypto/hypotheses/CRYPTO-004-maker-basis-carry.md`.
2. **Code Implementation:** `src/titan/research/crypto_shadow_runner.py` implementing `CryptoShadowRunner`, `get_shadow_status()`, and `export_shadow_evidence()`.
3. **Automated Verification:** Comprehensive test suite in `tests/research/test_crypto_shadow_runner.py` covering event ingestion, maker fill simulation, legging timeout fallback, funding accrual, evidence export, and execution import ban.
4. **Monitoring:** Real-time metrics tracking `maker_fill_rate`, `mean_unhedged_duration_min`, `unrealized_basis_pnl`, and `cumulative_net_pnl`.

---

## Approval

Accepted 2026-09-01 by Architecture Council and Risk Owner.
