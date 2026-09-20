# ADR-033: Cross-Market Alpha Research Admission and Governance Boundary

> Renumbered from ADR-032 (2026-09-20): the 032 slot was already taken by the
> accepted ADR-032-crypto-004-shadow-deployment record when this proposal was drafted.

- **Status:** Proposed (2026-08-28) — Architecture Council and Risk Owner review
- **Date:** 2026-08-28
- **Owners:** Research Platform, Architecture Council, Risk Owner
- **Decision scope:** Cross-market information transmission, macro-surprise response, and structural dislocation research only
- **Supersedes / superseded by:** Complements ADR-0005, ADR-0006, ADR-026, ADR-028, ADR-029, ADR-030, and ADR-031; establishes admission gates preventing infrastructure construction prior to validated data and causal mechanism screens.

---

## Context

Previous extensive empirical discovery programs on liquid FX (single-pair OHLCV momentum, mean reversion, carry, vol-carry), US Equities cross-sectional factors (12-1M momentum, short-term reversal, low-vol), and Crypto perpetual futures terminated with absorbing negative results due to execution spread friction, lack of cointegration, and noise mining.

Project TITAN requires a formal framework to evaluate whether **Cross-Market Alpha**—defined as a measurable, causal information transfer or structural dislocation across instruments—is admissible for empirical investigation without violating past terminal findings or triggering premature platform construction.

---

## Invariants & Core Principles

1. **Absorbing Terminal Boundaries:**
   - All past terminal rejections (e.g., `EXP-00016` through `EXP-00027`, `CRYPTO-001` through `CRYPTO-003`, and pure liquid-OHLCV directional indicators) remain absorbing for their registered hypothesis IDs and signal families.
   - Cross-market research cannot repackage, invert, retune, relax cost models for, or extend those failures.

2. **Strict Definition of Cross-Market Alpha:**
   - 'Cross-market alpha' means a measurable, causal, cross-instrument transfer or dislocation that is **not** a directional liquid-OHLCV pattern.
   - It is neither a portfolio diversification claim, a correlation mining exercise, nor an execution/order-routing program.

3. **Read-Only Research Authority:**
   - Research authority is strictly read-only.
   - No credentials, broker adapters, `TradeIntent` emissions, portfolio/risk state modifications, paper accounts, order paths, `PromotionCertificate` alterations, or live capital authority are granted by this ADR.

4. **Data Contract Prerequisite:**
   - Point-in-time (PIT) data must be verified and checksummed before any hypothesis evaluation begins.
   - Requirements include: provider/licence verification, PIT availability timestamps, UTC alignment, symbol/contract mapping, corporate actions / revisions treatment, survivorship bias elimination, SHA-256 manifests, and retention policies.
   - The absence of an admissible data contract constitutes an immediate pre-experiment rejection.

5. **Preregistration & Quantitative Gates:**
   - Each admitted hypothesis must have a unique ID, explicit causal mechanism, falsifying counter-mechanism, exact universe, decision timestamp, lead/lag convention, frozen In-Sample/Out-of-Sample (IS/OOS) boundary, economic and random controls, capacity ceiling, and immutable cost model declared before OOS evaluation.

6. **High-Fidelity Cost & Friction Attribution:**
   - Simulations must use executable quote-sided prices (bid/ask) and separately attribute gross mechanism return, spread, broker commissions, market impact, short-borrow fees, financing drag, data latency, and legging/hedge slippage.
   - Bar-close constant-bps assumptions are exploratory only and disqualified from progression.

7. **Terminal Negative Result Preservation:**
   - Any hypothesis failing quantitative OOS gates is permanently preserved as a `negative_result` (`mechanism_failure` or `execution_constrained_rejection`).
   - Positive OOS candidates are eligible solely for shadow-mode observation proposals under separate council review.

---

## Admission Scope & Sequence

1. **Step 1: Data Availability & Causal Mechanism Screen:**
   - Must utilize information sources absent from failed liquid-OHLCV searches: timestamped macro/fundamental surprise data, synchronized cross-venue/cash-futures/ETF quotes, or validated participant order-flow / book data.
2. **Step 2: Prioritized Candidate Hypothesis (`CM-001`):**
   - Focus exclusively on scheduled, timestamped US Macro Surprise transmission (e.g., Non-Farm Payrolls, CPI, Rate Decisions) across liquid US ETF pairs (e.g., SPY, QQQ, TLT, XLF).
   - Requires verified consensus releases, timestamped revision fields, and millisecond-synchronized quote prices.
3. **Step 3: Deferred Candidates:**
   - Cash-futures/ETF basis dislocations and market-structure flow hypotheses remain deferred until independent data quality, licensing, capacity, and venue risk reviews are ratified.
   - Crypto perps remain governed by ADR-029; `CRYPTO-001`..`003` stay permanently closed.

---

## Alternatives and Trade-offs

- **Directional Trend-Following Extension:** Rejected. Liquid FX and single-asset trend following are empirically exhausted in TITAN's operational parameter space.
- **Unconstrained Cross-Asset Statistical Arbitrage (Pairs / Cointegration Mining):** Rejected due to high risk of spurious correlation and sudden cointegration breakdown during regime shifts.
- **Infrastructure-First Construction:** Rejected. No new adapters, execution engines, or streaming servers will be built without a statistically validated OOS alpha candidate.

---

## Validation and Evidence

Required artifacts before Phase 2 acceptance:
1. `research/CROSS_MARKET_ALPHA_CHARTER.md`: Comprehensive governance charter, hypothesis registry, and frozen decision gates.
2. Verified point-in-time data contract and manifest (`research/cross_market/manifests/`).
3. Preregistration document for `CM-001` with explicit economic mechanism and OOS test dates.
4. Negative result archive structure ensuring absorption of failed runs.
