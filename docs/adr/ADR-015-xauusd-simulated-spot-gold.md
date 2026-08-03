# ADR-015: XAUUSD simulated spot-gold contract

- **Status:** Accepted
- **Date:** 2026-07-20
- **Owners:** Architecture Council, Risk Owner
- **Decision scope:** XAUUSD spot gold — simulated and backtest environments only
- **Supersedes / superseded by:** None

## Context

XAUUSD is one of the most liquid USD-quoted instruments globally, providing independent strategy research diversification beyond equities and forex. Adding a spot-metal contract tests the asset-class abstraction without requiring a live broker. No existing `ContractType` accurately represents a spot metal — `Forex` implies a currency pair, `Stock` implies equity.

## Evidence

- `contracts/README.md` and research on spot gold as a USD-quoted commodity.
- XAUUSD daily OHLC data is available from Polygon.io and Alpha Vantage.
- Spot gold trades 23h/day, Sun–Fri, with a daily maintenance break — only daily weekday bars are used for research.

## Decision

1. Add `Commodity` variant to `ContractType` enum in the Rust core.
2. Adopt `XAUUSD` as the first spot-metal instrument with `step_size=1` (one troy ounce), `tick_size="0.01"`, and quote currency USD.
3. Simulation and backtest only — no live or Alpaca-paper routing. The engine rejects unregistered instruments before any adapter call.
4. Only opening buys are permitted — a sell must reduce an existing long position.
5. Data uses daily weekday bars with optional volume.
6. No leverage, financing, rollover, or shorting.

## Alternatives and trade-offs

- **Reuse `ContractType::Forex`** — Rejected. Gold is not a currency pair. A separate variant keeps the domain model explicit and prevents forex-specific logic (pip calculations, lot conventions) from applying to metals.
- **Reuse `ContractType::Stock`** — Rejected. Gold has no corporate actions, dividends, or voting rights. Mixing equity and commodity semantics creates confusion in position/PnL reporting.
- **No new variant, use string tags** — Rejected. ADR-0001 requires typed contracts. String tags bypass compiler checks and allow silent misrouting.
- **Add XAGUSD, XPTUSD now** — Deferred. Start with gold only; add other metals when explicitly needed.
- **Build IBKR adapter with gold support** — Deferred. IBKR supports spot gold but requires full adapter development. Simulation-first validates the contract type and data pipeline.

## Consequences

- `ContractType` gains one new variant — all existing Rust pattern matches need updating (the compiler enforces this).
- The engine now requires instrument registration for all types — unregistered intents are rejected. This changes behavior for forex and equity instruments too (safe: they are always registered in practice).
- Spot gold uses 1-ounce steps vs. forex's 1000-unit micro-lots — strategies must be aware of the quantity convention change.
- No existing code is broken — the new variant defaults to current behavior in risk/portfolio code.

## Validation and operations

- Python test verifies `ContractType.Commodity` is exposed via PyO3.
- Instrument factory test verifies `XAUUSD` uses `ContractType::Commodity`, correct tick/step/precision.
- Engine test verifies unregistered instrument rejection.
- Backtest verifies BUY 1 → SELL 1 round-trip is flat with reproducible PnL.
- Metrics `spot_metal.*` are emitted on intent and rejection.
- Rollback: remove `Commodity` from the enum, delete `spot_metals.py`, revert normalizer, remove engine registration check. Rust recompilation required.

## Approval

Architecture Council and Risk Owner — 2026-07-20
