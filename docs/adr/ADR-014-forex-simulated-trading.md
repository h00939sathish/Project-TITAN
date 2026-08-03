# ADR-014: Adopt forex for simulated trading

- **Status:** Accepted
- **Date:** 2026-07-20
- **Owners:** Architecture Council
- **Decision scope:** Forex pair trading — simulated and backtest environments only
- **Supersedes / superseded by:** None

## Context

The project currently supports US equities and ETFs only. Forex pairs are a natural expansion for strategy research — they offer 24/5 continuous trading, a different market microstructure, and additional diversification for strategy validation. The Rust core already contains a `ContractType::Forex` variant but it has never been wired into any instrument definitions, adapters, or data pipelines.

Expanding to forex in simulation allows the platform to validate its asset-class abstraction layer before the complexity of a live IBKR integration.

## Evidence

- `core/src/types.rs:168-175` — `ContractType::Forex` defined at line 174, alongside Stock, Option, Future, and Crypto.
- `docs/scope/operating-scope.md:38` — Forex explicitly excluded from initial scope: "Brokers with quality paper forex are rare."
- `docs/scope/broker-capability-register.md:28` — Alpaca has no forex support.
- `docs/scope/broker-capability-register.md:47` — IBKR supports forex, but requires full IBKR adapter development.
- `docs/scope/data-source-register.md:45,64` — Both Polygon.io and Alpha Vantage offer forex OHLC data.

## Decision

1. **Pairs.** Adopt four USD-quote forex pairs: EUR/USD, GBP/USD, AUD/USD, NZD/USD. Pairs with non-USD quote currencies (USD/JPY, USD/CHF, USD/CAD) are excluded — their PnL is denominated in JPY/CHF/CAD and the portfolio engine is USD-only. Add them when multi-currency portfolio valuation (FX rate provider, quote-currency PnL conversion) is implemented.
2. **Quantity convention.** 1 unit = 1000 base currency (micro-lot); `step_size = 1000`; all order quantities must be multiples of 1000.
3. **No leverage.** Trades sized against cash balance only — no margin expansion.
4. **No live broker.** Simulated and backtest execution only. Live forex requires a future IBKR adapter ADR.
5. **Data.** OHLC sourced from Polygon.io or synthesized fixtures. Volume is optional (forex volume is tick count and not meaningful for most strategies).
6. **Calendar.** Forex 24/5 calendar (Mon–Fri) replaces the US equities calendar for forex instruments.

## Alternatives and trade-offs

- **Extend Rust types with new variants.** Rejected — `ContractType::Forex` already exists and is compiled. No Rust changes needed in this phase.
- **Build IBKR adapter now.** Deferred. IBKR integration is complex (TWS/IBGW API, multiple asset classes, compliance setup). A dedicated Phase L+ ADR will cover it. Simulation-first lets us validate forex instrument semantics and strategy compatibility before committing to live broker engineering.
- **Fractional quantities.** Rejected. Micro-lots (1000 base currency) are the industry standard minimum for retail forex; fractional microlots add complexity without a demonstrated need.
- **Include exotic pairs.** Deferred. The four USD-quote pairs cover the most liquid segment of forex that is safely modelable with USD-only accounting. Exotics add wider spreads, lower liquidity, and multi-currency PnL — deferred until multi-currency valuation exists.

## Consequences

- **Quantity semantics differ from equities.** Equities use 1-unit steps; forex uses 1000-unit steps. The instrument definition carries `step_size` so the execution engine, risk checks, and position sizing must respect it.
- **Forex 24/5 calendar.** All existing calendar logic assumes US equities (NYSE/NASDAQ holidays, 9:30–16:00 ET). Forex instruments use a separate calendar: weekdays are trading days, weekends are closed. No US holiday observance.
- **No meaningful volume.** Forex data from Polygon.io and Alpha Vantage reports volume as tick count, not contract volume. The data normalizer treats volume as optional for forex pairs.
- **Existing strategies work unchanged.** Moving-average crossover, mean reversion, and other price-series strategies operate on OHLC data. Changing from an equity symbol to a forex symbol requires no strategy code changes — only instrument registration changes.
- **Scope document updated.** `operating-scope.md` now lists forex as in-scope for simulated trading with the micro-lot convention.

## Validation and operations

- Forex instrument creation tests pass: `forex_instrument(symbol)` returns a valid Instrument with `ContractType::Forex` and correct tick/step sizes.
- Forex backtest produces deterministic results: identical inputs → identical event stream, PnL, and metrics.
- Data normalizer accepts forex OHLC bars with and without volume fields.
- Simulated adapter accepts forex orders and returns fills with correct quantities.
- Rollback: delete forex instrument definitions, revert calendar, remove forex symbols from normalizer — no Rust core changes to revert.

## Approval

Architecture Council — 2026-07-20
