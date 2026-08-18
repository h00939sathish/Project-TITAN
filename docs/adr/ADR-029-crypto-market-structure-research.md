# ADR-029: Authorize a bounded crypto market-structure research program

- **Status:** Accepted (2026-08-14) — Architecture Council and Risk Owner
- **Date:** 2026-08-13
- **Owners:** Research Platform, Architecture Council, Risk Owner
- **Decision scope:** crypto data acquisition, research simulation, and validation only
- **Supersedes / superseded by:** extends neither execution nor paper-trading scope; complements ADR-0005, ADR-0006, ADR-026, and ADR-028

## Context

The FX/spot-gold liquid-OHLCV search is terminal with no qualified strategy. The terminal report identifies microstructure, order-flow, and cross-sectional data as untested classes requiring new evidence. Crypto perpetual markets expose possible structural inputs—funding, basis, open interest, taker flow, liquidation events, and order-book states—but crypto is explicitly excluded from the current operating scope because it is 24/7/365, venue-specific, and has distinct regulatory and operational risks.

## Evidence

- `research/ALPHA_SEARCH_TERMINAL_REPORT.md`: simple liquid-OHLCV signal families produced no survivor; new data classes are required.
- `docs/scope/operating-scope.md`: crypto is excluded from the initial operational scope.
- `docs/reference/BACKTEST_ENGINE.md`: venue/instrument-aware executable-price, fee, latency, liquidity, and lower-fidelity requirements apply to any new simulation domain.
- Current source inspection: no crypto feed, venue adapter, calendar, instrument definitions, fee/funding model, fractional sizing path, or crypto-specific tests exist.

## Decision

1. Authorize a **research-only discovery sprint** for BTC and ETH spot/perpetual market structure. No exchange credentials, orders, paper accounts, adapters, or certificate issuance are permitted by this ADR.
2. Before data acquisition, register the selected venue(s), licence/terms, symbols, time zone, timestamps, fee schedules, funding convention, margin/contract definitions, and data retention/provenance. Start with read-only historical data.
3. Test only pre-registered structural hypotheses: cross-sectional funding/basis carry; funding/open-interest deleveraging; and order-flow or liquidity imbalance. Indicator-only variations of the retired FX OHLCV strategy families are excluded.
4. Use a point-in-time, 24/7 venue-aware simulator. Net performance includes bid/ask executable prices, maker/taker fees, funding, borrow where applicable, latency, partial fills/participation, contract multipliers, fractional precision, and adverse venue-disconnect assumptions.
5. Require at least 24 contiguous months of data including inactive/delisted eligible instruments where the hypothesis requires a universe. Define IS/OOS partitions and pass/fail criteria before reading the OOS segment.
6. Terminal outcome is either one reproducible net-of-cost candidate eligible for a future shadow-only proposal, or a negative-result record. Neither outcome authorizes paper or live crypto trading.

## Alternatives and trade-offs

- **Port existing technical indicators to crypto candles:** rejected as the same low-information OHLCV search class already failed.
- **Connect an exchange/paper account first:** rejected because execution capability is not evidence of alpha and crypto is out of operating scope.
- **Use free endpoint snapshots as a long-history research source:** rejected unless their coverage, corrections, and historical completeness satisfy the data contract.

## Consequences

Positive: the program tests a genuinely different hypothesis/data class while preserving TITAN's fail-closed capital boundary. Negative: quality historical market-structure data may require a budget; exchange data quality and venue discontinuities can invalidate a result; no result is expected or implied.

## Validation and operations

Required acceptance evidence: a data-source manifest; time/order/correction quality report; static venue capability and cost snapshots; crypto calendar/instrument contract tests; funding/fee/precision simulation tests; a pre-registered walk-forward artifact; and a reproducible negative or candidate evidence bundle. Metric/report fields include net PnL attribution for price, funding, fees, spread, impact, and failed/partial fills.

Rollback stops research ingestion and retains immutable manifests and experiment artifacts. This ADR cannot be used to enable exchange credentials, orders, paper trading, or live trading; those require a separate accepted scope ADR, broker certification, and ADR-028 certificate controls.

## Approval

Accepted 2026-08-14 by Architecture Council and Risk Owner (human owner).
