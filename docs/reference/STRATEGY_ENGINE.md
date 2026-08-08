# Strategy Engine

> **Owner:** Quantitative Research Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Strategy Owner; Risk Owner for activation
> **Depends On:** [RESEARCH_ENGINE.md](RESEARCH_ENGINE.md), [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [PORTFOLIO_ENGINE.md](PORTFOLIO_ENGINE.md)
> **Supersedes:** None
> **Review Frequency:** Per strategy-interface change; quarterly otherwise

## Strategy contract

A strategy is an immutable, versioned package that consumes approved market/feature events and emits only `TradeIntent` under [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md). It never invokes a broker, calculates authoritative portfolio state, changes limits, or bypasses the risk gate. This preserves the selected strategy strengths while avoiding distributed risk logic noted in `../STRATEGY_ENGINE_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

## Package manifest

Each package declares package id/version/digest; owner; research hypothesis and experiment ids; universe; supported venues/accounts; required data/feature schemas; deterministic parameter schema with defaults/ranges/units; schedule; signal/output semantics; order-instruction constraints; risk-profile version; portfolio compatibility constraints; telemetry; test fixtures; and activation/retirement criteria. A package version cannot change semantics after registration; publish a new version and preserve compatibility/migration evidence.

## Lifecycle

`Draft → Registered → Validated → PaperActive → RestrictedLive → Active → Reducing → Suspended → Retired`. Validation evidence accompanies every transition. `Suspended` blocks new intents; `Reducing` requests only policy-permitted reduction intents. Activation requires the strategy package, configuration digest, target allocation, and risk profile to be approved together. Retirement cancels new scheduling, preserves the package/data/results, and documents performance/operational reason.

## Parameters and ensembles

Parameters are typed, bounded, unit-bearing, and immutable per run; optimization emits a new candidate parameter set with lineage, never mutates a live package. An ensemble is a versioned portfolio of strategies with membership, correlation/diversification evidence, allocation policy, common-risk constraints, rebalance rule, and failure behavior. Ensemble allocation is advisory until accepted by [PORTFOLIO_ENGINE.md](PORTFOLIO_ENGINE.md); a constituent failure cannot silently redistribute capacity beyond approved bounds.

## Portfolio compatibility

Before an intent is emitted, a strategy validates its own data/feature freshness, instrument/venue eligibility, package activation, and local invariant checks. The Portfolio and Risk engines remain authoritative for account, currency, margin, exposure, concentration, turnover, liquidity, and hard limits. Incompatible strategy/portfolio versions, stale features, or unknown package identity fail closed and are observable.

