# Strategy Runtime Specification

> **Owner:** Strategy Runtime
> **Status:** Active — Phase J (multi-timeframe)
> **Last Review:** 2026-07-24
> **Supersedes:** Single-timeframe (daily-only) runtime specification
> **Implemented in:** `src/titan/strategies/multitimeframe_runtime.py`, `src/titan/runtime/evaluator.py`, `src/titan/runtime/events.py`

## Purpose

Define the deterministic boundary between event producers (strategies, advisory agents) and `TradeIntent` emission. The runtime may propose intents only; it does not own portfolio state, broker access, risk decisions, or order routing.

## Boundary / Ownership

Owns: event dispatch, trigger matching, per-(producer, instrument, timeframe) state isolation, warmup, signal function lifecycle, and construction of typed `TradeProposal` objects.

Delegates to: `ProposalValidator` for proposal validation, `PaperTradingEngine.submit_intent()` for all broker interaction, portfolio reconciliation for starting position state.

Called by: the session runner on each `MarketEvent`.

## Inputs

- `MarketEvent` with typed payload (BarClosed, Tick, Heartbeat, BrokerFill, AdvisoryProposal, etc.). Every event carries `message_id`, `causation_id`, `correlation_id`, `occurred_at`, `received_at`, `schema_version`, `source`, `event_type`, `instrument_id`, and payload digest.
- `StrategyDefinition` per registered producer: `strategy_id`, exactly one `TriggerSpec(event_type, timeframe)`, and an immutable `context` tuple of additional timeframes available as read-only data.
- `FeatureSnapshot` — current derived bar values per instrument and resolution.
- Immutable `PortfolioContextSnapshot` reference (read-only for producers).
- Warmup price history per (strategy_id, instrument_id, timeframe).

## Outputs

- At most one `TradeProposal` per (producer_id, instrument_id, timeframe, close_timestamp).
- Proposals contain `producer_kind`, `package/model/prompt digest`, `sources`, `expiration`, `requested action`, and `rationale digest`.
- No direct broker call, portfolio mutation, risk override, or secret access.
- `TradeProposal` must pass `ProposalValidator` before becoming `TradeIntent`.

## Supported timeframes

- `FIVE_MINUTES` — 5-minute closed bars
- `FIFTEEN_MINUTES` — 15-minute closed bars
- `ONE_HOUR` — 1-hour closed bars
- `ONE_DAY` — daily closed bars

Mapped via `Timeframe.from_duration(duration: timedelta)` in `src/titan/strategies/timeframes.py`.

## Trigger semantics

1. Each `StrategyDefinition` declares exactly one `TriggerSpec(event_type, timeframe)`.
2. On `MarketEvent` arrival, `RuntimeEvaluator` checks every registered definition.
3. Only definitions whose `TriggerSpec` matches the event's `event_type` and `timeframe` are evaluated.
4. Auxiliary context timeframes never create an implicit trigger.
5. BarClosed is the only trigger that produces `TradeProposal`. Tick, Heartbeat, and BrokerFill events update state but do not (by default) trigger evaluation.

## Warmup and startup semantics

1. The session runner warms each (strategy_id, instrument_id, timeframe) with every bar before the current bar.
2. Warmup never constructs a `TradeIntent`.
3. Warmup records the most recent directional signal per tuple.
4. Position state is reconciled from the portfolio before processing the first current bar.

## State isolation

Indicator state, warmup direction, position state, and deduplication state are keyed by `(strategy_id, instrument_id, timeframe)`. No state crosses timeframes.

## Failure behavior

| Condition | Runtime behavior | Downstream behavior |
|---|---|---|
| Unsupported bar duration | Reject bar, emit alert | No proposal; alert logged |
| Stale data (exceeds TTL per timeframe) | Emit no proposal | Session remains active; data freshness alert |
| Duplicate (id, instrument, timeframe, timestamp) | Emit no proposal | No duplicate broker submission |
| Unqualified (strategy, timeframe, params) | Emit no proposal | Gate blocks activation |
| SELL while flat | Emit no proposal | No unauthorized short is opened |
| ProposalValidator rejects | Do not retry from runtime | Engine records the typed rejection |
| Advisory producer submits TradeIntent | Reject; advisory may only propose | Deterministic validation must construct intent |

## Monitoring and rollback

- **Per-timeframe metrics:** closed bars received, runtime evaluations, proposals created, proposals accepted/rejected, event lag, data freshness.
- **Alerts on:** zero evaluations in an expected session, proposal from a disabled timeframe, duplicate-bar proposal.
- **Rollback:** revert to daily-only polling loop, disable intraday timeframe declarations, remove intraday-qualified variants from registry. Kill switch is the emergency stop.

## Acceptance evidence

- `tests/strategies/test_timeframes.py` — every supported duration maps to the correct Timeframe; unsupported durations raise.
- `tests/strategies/test_multitimeframe_runtime.py` — state isolation, duplicate bars, stale data, warmup deduplication, SELL-while-flat, and provenance.
- `tests/runtime/test_evaluator.py` — trigger matching, no evaluation for non-matching timeframes, advisory proposal validation, heartbeat routing.
- `tests/runtime/test_events.py` — envelope validation, event ordering, causal correlation, producer permissions.
- No emitted proposal reaches a broker without passing `PaperTradingEngine.submit_intent()`.
