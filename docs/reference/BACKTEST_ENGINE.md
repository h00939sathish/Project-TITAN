# Backtest Engine

> **Owner:** Quantitative Research Infrastructure
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Research Owner; Reliability Owner for replay semantics
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [DATA_PIPELINE.md](DATA_PIPELINE.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md)
> **Supersedes:** None
> **Review Frequency:** Per simulation-semantic change; quarterly otherwise

## Purpose

The Backtest Engine deterministically replays point-in-time market/corporate-action data through the same contract-level strategy, risk, order, and portfolio semantics used in controlled operation. It is validation evidence, not a prediction oracle. Jesse-derived walk-forward and Monte Carlo methods are adopted as validation patterns, as supported by `../ADOPTION_DECISIONS.md`.

## Replay model

The clock advances by ordered event time. A run records source partitions, instrument mapping, calendar/timezone, strategy/package/config/risk versions, simulator version, seed, and complete emitted event stream. Determinism requires identical inputs to produce identical orders, fills, positions, PnL, and metrics. Corrections, late data, halts, session boundaries, splits/dividends, symbol changes, delistings, and cash actions are explicit events; the engine does not silently repair data.

## Execution simulation

Fill models are selected by venue/instrument and declared in the run: bar-conservative, quote-based, or order-book replay. A model specifies order priority, partial-fill rules, bid/ask spread, queue/participation assumption, liquidity cap, exchange/broker latency, rejection/cancel behavior, commission/tax/fee schedule, and currency conversion. Slippage and market impact are functions of executable price, volatility/liquidity, size, and participation—not optimistic constants. When order-book data is unavailable, the result is labelled lower-fidelity and cannot support a capacity claim.

## Validation and reporting

Runs report gross/net return, PnL attribution, drawdown, turnover, exposure, fill/reject/cancel profile, cost/impact, capacity proxy, benchmark comparison, regime breakdown, and all exceptions. Walk-forward windows, Monte Carlo perturbations, and adversarial cost/latency scenarios are predeclared. The result links to the research experiment, strategy package, data versions, and artifact digest. Any mismatch with production contract/replay behavior blocks promotion until explained by an approved ADR.

