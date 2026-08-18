# Architecture Council + Risk Owner — Crypto Market-Structure Review

- **Date:** 2026-08-13
- **Scope:** ADR-029 acceptance, CryptoResearch.spec.md acceptance, research-program flags
- **Materials:** [ADR-029](../../docs/adr/ADR-029-crypto-market-structure-research.md), [Charter](../../research/crypto/CRYPTO_MARKET_STRUCTURE_CHARTER.md), [Debated plan](plans/2026-08-13-crypto-market-structure-research.debated.md), [CryptoResearch.spec.md](../../specifications/CryptoResearch.spec.md)

## Context for the review

The FX/spot-gold liquid-OHLCV search is terminal with no qualified strategy. This program tests a genuinely different evidence class (market structure: funding, basis, open interest, order flow) with no execution capability attached. Per ADR-029, the program cannot begin until this review accepts the ADR and the specification lands with it. The implementation plan has passed a two-cycle multi-model debate plus a second-round charter-conformance review; no contradictions with ADR-029 or the charter remain.

## Agenda

1. **Motion 1 — Accept ADR-029** (bounded crypto market-structure research program; research-only).
2. **Motion 2 — Accept CryptoResearch.spec.md** (boundary, event contract, state machine, error taxonomy, metrics, rollback).
3. **Motion 3 — Acknowledge the six plan flags** with dispositions below.
4. Next steps: venue/data-source selection, licence review, budget note, registry skeleton.

## Decision record

| Motion | Decision | Approver / date |
|---|---|---|
| 1. ADR-029 accepted | ☐ Accept ☐ Reject ☐ Amend (state) | Architecture Council ____  Risk Owner ____ |
| 2. CryptoResearch.spec.md accepted | ☐ Accept ☐ Reject ☐ Amend (state) | Architecture Council ____  Risk Owner ____ |
| 3. Flags acknowledged | ☐ As disposed below ☐ Other (state) | Architecture Council ____ |

## Flag dispositions (Motion 3)

| # | Flag | Default disposition (accept unless noted) | Council decision |
|---|---|---|---|
| 1 | Capacity gate literal text is weak ("capacity positive") | Accept literal gate; capacity curve reported in results; consider ≥0.5% of 30d ADV floor as a later ADR-029 amendment | ☐ |
| 2 | Secondary-venue replication requires only net Sharpe > 0, not all five gates | Accept narrowed criterion; full re-qualification would need an ADR-029 amendment | ☐ |
| 3 | Re-registration permitted after primary-pass + secondary-failure | Accept re-registration under a new hash; terminal stop requires a stated preference | ☐ |
| 4 | Order-flow invalidation threshold (3 expected update intervals) is uncalibrated | Accept default; venue-specific thresholds may follow once venues are chosen | ☐ |
| 5 | Delisting force-close applies a 2× spread penalty | Confirm conservative; adjust only if Council specifies | ☐ |
| 6 | Sharpe bootstrap block length 10 days | Accept default; sensitivity sweep optional before OOS read | ☐ |

## Next steps after acceptance

1. Select venue(s) and data source(s); review licence/terms and retention; note budget (ADR-029: quality historical data may require budget). Record in venue registry.
2. Draft registry skeleton and pre-registration artifact template (Task 0 material) — documents first, no acquisition.
3. Open implementation only after this record is complete: Task 1 contracts and fixtures, then read-only ingestion.
4. Execution denial restated: nothing in these materials authorizes credentials, orders, paper accounts, adapters, certificates, or live trading. Those require a separate accepted scope ADR, broker certification, and ADR-028 certificate controls.
