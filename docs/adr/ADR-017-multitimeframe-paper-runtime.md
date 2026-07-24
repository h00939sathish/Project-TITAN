# ADR-017: Multi-timeframe paper runtime

- **Status:** Draft
- **Date:** 2026-07-24
- **Owners:** Architecture Council
- **Decision scope:** Strategy evaluation frequency, bar subscription, broker adapter interface, activation gates for intraday tuples
- **Supersedes / superseded by:** None

## Context

The Phase J paper session evaluates all strategies on daily closes only. Every strategy declares no trigger and the session loop polls on a fixed interval, waiting for the daily candle to close before any evaluation occurs. This design has three limitations:

1. **All strategies share one trigger.** A swing strategy and a momentum strategy both evaluate on the daily close, even though one might benefit from intraday signals.
2. **No event-driven evaluation.** Bar arrival does not trigger evaluation; the session loop polls and skips bars until 16:01 ET.
3. **No broker-agnostic adapter contract.** The existing `ibkr_paper_session.py` bypasses `PaperTradingEngine.submit_intent()` and calls Nautilus's `self.submit_order()` directly, circumventing TITAN's risk gate, event store, and reconciliation path.

The feedback in `docs/superpowers/plans/2026-07-24-safe-multitimeframe-paper.md` identifies the core architectural gap: strategy triggers should be declarative, not implicit.

## Evidence

- `scripts/paper_session.py:581-623` — the polling loop with `time.sleep(60)` and daily-bar guard.
- `scripts/ibkr_paper_session.py:250-256` — direct Nautilus order path without TITAN risk gate.
- `src/titan/strategies/bridge.py` — no timeframe parameter; assumes daily bars.
- `src/titan/strategies/registry.py` — no qualified-timeframe metadata.
- `docs/scope/operating-scope.md:68-78` — daily-only trading frequency.
- `specifications/StrategyRuntime.spec.md` — daily-only inputs, no timeframe isolation.
- Reviewer feedback (2026-07-24): identifies 1-DAY-only trigger as the primary limitation.

## Decision

1. **Declared triggers replace implicit polling.** Every strategy or producer declares exactly one `TriggerSpec` (event type + timeframe). Evaluation fires only when a matching event arrives. No polling loop.

2. **Timeframe is a canonical enum.** `Timeframe.from_duration(duration)` maps a `datetime.timedelta` to one of `FIVE_MINUTES`, `FIFTEEN_MINUTES`, `ONE_HOUR`, or `ONE_DAY`. String comparisons against "1-DAY" are replaced.

3. **State is isolated by (strategy, instrument, timeframe).** Indicator warm-up, position state, and deduplication state never cross timeframes. A strategy running on both 5m and 1D has independent state per resolution.

4. **All orders route through `PaperTradingEngine.submit_intent()`.** No strategy, session runner, or adapter may call a broker or Nautilus `submit_order()` directly. The risk gate, event store, and reconciliation path are mandatory.

5. **Activation gate for intraday tuples.** A (strategy, timeframe, parameters) tuple remains disabled until walk-forward, Monte Carlo, fee/slippage, data-quality, and paper-session evidence is recorded and approved by Strategy Owner and Risk Owner.

6. **The IBKR adapter uses `ibapi` directly, not Nautilus.** Implemented as `IBKRPaperAdapter(BrokerAdapter)` in `src/titan/execution/ibkr_adapter.py`. Nautilus is retained only for bar subscription as an alternative data ingress, not for order routing.

## Alternatives and trade-offs

- **Keep daily-only polling** — Rejected. Blocks the intraday and event-driven roadmap.
- **Build the feature graph first** — Deferred. Tick → 1m → 5m → 15m → 1h → 1d aggregation is architecturally desirable but not required for the core fix (declared triggers). The runtime can subscribe to independent bar resolutions without aggregating.
- **Use Nautilus for both data and execution** — Rejected. The existing `ibkr_paper_session.py` proved this bypasses TITAN's risk path. Nautilus is data-only.
- **No activation gate — trust daily evidence for intraday** — Rejected. Daily parameters have daily-only evidence. Intraday parameters require independent validation.

## Consequences

- `specifications/StrategyRuntime.spec.md` is updated to define multi-timeframe inputs, isolated state, and closed-bar-only evaluation.
- `docs/scope/operating-scope.md` adds intraday frequency with explicit constraints (regular US session only, certified paper notional only).
- `docs/runbooks/paper-session.md` is updated to document multi-timeframe operation and monitoring.
- `src/titan/strategies/timeframes.py` implements the `Timeframe` enum.
- `src/titan/runtime/events.py` and `src/titan/runtime/evaluator.py` implement the event-driven trigger scheduler.
- `src/titan/strategies/multitimeframe_runtime.py` implements per-timeframe state isolation.
- `src/titan/strategies/registry.py` gains `is_qualified_for(timeframe)`.
- Existing daily evidence still qualifies daily tuples. Intraday tuples require new evidence per the activation gate.

## Validation and operations

- **Metrics per timeframe:** closed bars received, runtime evaluations, proposals created, proposals rejected/accepted, event lag, data freshness.
- **Alert on:** zero evaluations in an expected session, proposal from a disabled timeframe, duplicate-bar proposal.
- **Rollback:** revert the runtime to the daily-only polling loop, remove intraday timeframe declarations from session config, disable intraday-qualified variants in registry. Kill switch remains the emergency stop.
- **Retirement trigger:** a superseding ADR that replaces the per-strategy trigger model with a fully general event-sourcing runtime.

## Approval

Architecture Council — pending

Risk Owner — pending
