# ADR-028: Require signed promotion certificates and canonical sizing before execution

- **Status:** Accepted
- **Date:** 2026-08-09
- **Owners:** Architecture Council, Risk Owner, Execution Platform, Research Platform
- **Decision scope:** strategy eligibility, `TradeIntent` provenance, paper/live order admission, sizing, promotion evidence, and research qualification history
- **Supersedes / superseded by:** complements ADR-022 through ADR-026; supersedes no accepted record

## Context

The alpha-search terminal report establishes that no strategy has current OOS evidence sufficient for promotion. The current implementation also has an integrity gap: the IBKR paper runner labels watchlist proposals as `shadow` but converts every proposal to a `TradeIntent` and calls `PaperTradingEngine.submit_intent`. Runtime eligibility is derived from code registration while historical qualification state remains in the research database. Research uses fixed quantities while runtime derives a percentage-of-equity quantity. These paths make shadow evidence, promotion, and execution non-comparable.

## Evidence

- `research/ALPHA_SEARCH_TERMINAL_REPORT.md`: no qualified strategy; alpha search closed.
- `scripts/ibkr_paper_session.py`: shadow-labelled proposals are submitted to the paper engine.
- `src/titan/research/harness.py` and `src/titan/strategies/multitimeframe_runtime.py`: sizing differs across research and runtime.
- ADR-022 through ADR-026: qualification and promotion controls must fail closed, retain evidence, and prevent unqualified execution.

## Decision

1. **Default deny.** No proposal may reach an order adapter unless an execution engine verifies a loaded, non-revoked, unexpired promotion certificate. The initial certificate registry is empty; the resulting paper/live execution state is no-order.
2. **Certificate authority.** Strategy registrations remain a code catalogue only. A certificate is canonical JSON with a SHA-256 content digest and an Ed25519 signature. It binds strategy/version, parameters, permitted instrument/timeframe/environment, package/data/cost-model/sizing digests, OOS evidence digest, expiry, revocation status, and two human approval identities. Its canonical public key is configured outside strategy code. Every certificate rejection is durable and reasoned.
3. **Layered shadow isolation.** A `shadow` proposal is written only to a shadow simulator/ledger. It is never transformed into an executable intent. Independently, the execution engine rejects an intent without a valid certificate, including if a caller regresses.
4. **Canonical sizing.** Research and runtime call one deterministic `Sizer`. It accepts a read-only equity snapshot, `notional_allocation_pct`, instrument price, conversion quote and timestamp, and lot step/minimum. It rejects missing/stale conversion data, invalid inputs, and allocations below a minimum lot; it rounds down and never forces a minimum quantity.
5. **Evidence.** Promotion gates consume persisted returns emitted by the canonical cost-aware simulator. Each artifact records the exact data, parameter, sizing, cost-model, IS/OOS-boundary, and package digests. Cost-free derived return series are not admissible evidence.
6. **Legacy records.** A dry-run-default, transactional, idempotent migration retains all historical qualification metrics and appends a status event retiring the three legacy `QUALIFIED` records with reason `Terminal report: structural integrity and cost-model violations`. Legacy records cannot be restored as execution authority.

## Alternatives and trade-offs

- **Caller-only shadow branch:** rejected because a future caller can bypass it.
- **Registry flags or research DB as eligibility:** rejected because mutable implementation/data state is not signed release authority.
- **Delete legacy rows:** rejected because it destroys audit evidence.
- **Fixed research quantity:** rejected because it breaks research-to-runtime parity.

## Consequences

Positive: no shadow strategy or legacy status can authorize an adapter call; paper evidence is attributable and comparable. Negative: no existing strategy can execute, new certificate/signature handling adds operational work, and historic return magnitudes change under canonical sizing.

## Validation and operations

Required tests: shadow adapter isolation; unsigned/forged/expired/revoked/mismatched certificate rejection; research/runtime sizing parity; underfunded and stale-FX sizing rejection; migration dry-run, commit, idempotence, and audit retention; and a clean build from a pinned toolchain. Monitor `shadow_proposals_total`, `shadow_ledger_writes_total`, `shadow_adapter_submission_total` (must remain zero), `certificate_rejections_total{reason}`, and `certificate_validation_latency`.

Rollback disables execution admission and preserves certificates, shadow evidence, migration backups, and audit events. Recovery requires a newly issued certificate; it never restores legacy eligibility.

## Approval

Architecture Council and Risk Owner must accept this ADR, the updated specifications, test plan, rollback, and monitoring design before implementation.
