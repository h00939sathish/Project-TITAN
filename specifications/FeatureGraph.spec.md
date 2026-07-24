# FeatureGraph Specification

> **Owner:** Strategy Runtime
> **Status:** Active — Phase J (multi-timeframe)
> **Last Review:** 2026-07-24
> **Implemented in:** `src/titan/runtime/feature_graph.py`

## Purpose

Derive higher-resolution bars (5m, 15m, 1h, 1d) deterministically from a single lower-resolution canonical stream per instrument. The graph enforces source consistency — ticks and external bars cannot be mixed for the same instrument — and provides read-only derived snapshots.

## Boundary / Ownership

Owns: bar derivation from ticks (→1m→5m→15m→1h→1d), source-kind enforcement, per-instrument isolation.

Called by: `RuntimeEvaluator.on_market_event()` to produce `FeatureSnapshot` views.

## Inputs

- `MarketEvent(event_type="Tick")` — contains `payload["price"]` and `occurred_at` for timestamp.
- `MarketEvent(event_type="BarClosed")` — accepted only when no Tick events have been seen for the same instrument. Contains `payload["timeframe"]` (Timeframe), `payload["close"]`, optional `open`, `high`, `low`, `volume`.

## Outputs

- `BarSnapshot(open, high, low, close, timestamp, volume=0)` per (instrument, timeframe).

## State machine

```
IDLE → (first Tick for instrument) → TICK_SOURCE
IDLE → (first BarClosed for instrument) → BAR_SOURCE
TICK_SOURCE → TICK_SOURCE on subsequent Tick
TICK_SOURCE → raise SourceConsistencyError on BarClosed
BAR_SOURCE → BAR_SOURCE on subsequent BarClosed
BAR_SOURCE → raise SourceConsistencyError on Tick
```

## Derivation chain

- Tick → ONE_MINUTE: ticks grouped by minute bucket (timestamp truncated to minute). First tick in bucket sets `open`; each subsequent tick updates `high`, `low`, `close`.
- ONE_MINUTE → FIVE_MINUTES: 5 consecutive 1m bars → OHLC aggregated (open=first.open, high=max(high), low=min(low), close=last.close).
- FIVE_MINUTES → FIFTEEN_MINUTES: 3 bars of 5m → OHLC aggregated.
- FIFTEEN_MINUTES → ONE_HOUR: 4 bars of 15m → OHLC aggregated.
- ONE_HOUR → ONE_DAY: 7 bars of 1h → OHLC aggregated.

Derivation is lazy: higher-resolution bars are computed on first access via `bar()`.

## Errors

| Failure | Raised When |
|---|---|
| `SourceConsistencyError` | Tick followed by BarClosed (or vice versa) for same instrument |
| `KeyError` | Requested Timeframe has no derivation path and no direct source |

## Metrics and acceptance evidence

- `test_ticks_derive_stable_five_minute_then_hourly_bars` — 60 ticks produce 12 5m bars and 1 1h bar with correct OHLC.
- `test_graph_rejects_mixed_external_and_derived_sources` — Tick + external BarClosed raises `SourceConsistencyError`.
- `test_one_minute_from_ticks` — Ticks → 1m bar.
- `test_empty_graph_returns_none` — No data → `bar()` returns `None`.
- `test_graph_digest_replay` — Same tick sequence twice produces identical bars.
- `test_missing_source_marks_dependent_stale` — Insufficient lower bars → higher resolution returns `None`.
