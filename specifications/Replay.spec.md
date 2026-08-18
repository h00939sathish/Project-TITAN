# Replay Specification

> **Owner:** Quantitative Research Infrastructure
> **Status:** Active — Phase -1
> **Last Review:** 2026-07-13
> **Supersedes:** None
> **Implemented in:** Phase D (platform/backtest/)

## Purpose

Deterministically replay point-in-time market and corporate-action data through the same contract-level strategy, risk, order, and portfolio semantics used in operation. The replay engine is validation evidence, not a prediction oracle.

## Boundary / Ownership

Owns: Replay clock, fill models, result collection, determinism invariants.
Delegates to: Event store (read), Strategy runtime (produce intents), Risk gate (evaluate), Portfolio (record), Data pipeline (normalized input).
Called by: Research engine (experiment runs), Validation (backtest/WFO/MC).

## Inputs

- Normalized market data (bars, trades, quotes) as Parquet
- Corporate action events (splits, dividends, symbol changes)
- Strategy package (digest, parameters, signal logic)
- Configuration: fill model, costs, slippage, calendar

## Outputs

- Complete emitted event stream (every intent, decision, order event, fill, position change)
- Result metrics: return, drawdown, Sharpe, turnover, fill profile, costs
- Artifact digests linking data, config, strategy, and fill model versions

## Determinism invariant

Identical inputs (data partitions, strategy package digest, parameters, seed, fill model config) must produce identical:
- Event stream (byte-for-byte identical event sequence)
- Positions at every point in time
- Final PnL and metrics
- Any exception (identical failure at identical event)

## Fill models

| Model | Input data | Fidelity | When to use |
|---|---|---|---|
| Bar-conservative | OHLCV bars | Low | Initial validation, large universes |
| Quote-based | Bid/ask quotes | Medium | Strategy depends on spread |
| Order-book replay | L2/L3 order book | High | Latency-sensitive strategies |

Order-book simulation and impact calibration are deferred until Phase F gate.

## Canonical FX Simulation (ADR-031 Amendment)

`FxCostModel`: `version`, `venue`, `account_currency`, `quote_currency`, `commission_bps`, `minimum_commission`, `half_spread_bps`, `slippage_bps`, `fill_mode`, `data_manifest_digest`.

- Canonical runs require `Decimal` values and a SHA-256 digest of the complete model.
- Commission is assessed on every fill as `max(notional_usd * commission_bps / 10_000, minimum_commission)`.
- `BAR_NEXT_OPEN` fills the order generated at bar *t* on bar *t+1* open plus adverse synthetic spread/slippage. It carries lower fidelity and cannot qualify or promote a candidate.
- `QUOTE_NEXT_EVENT` fills buy at ask and sell at bid using next-event quote data.
- Missing required price, quote, or USD conversion rejects the run fail-closed.
- Promotion gate rejects artifacts with missing digests, mismatched digests, or lower-fidelity fill models.

## Corporate actions

Each action is an explicit event applied at its effective time:
- **Split**: adjust position quantity and reference price; no PnL impact.
- **Dividend**: cash adjustment; realized PnL impact.
- **Symbol change**: update instrument identifier.
- **Merger/delisting**: close position at determined price; realized PnL.

The engine does not silently repair data. Correction events are applied with lineage.

## Dependencies

- Data pipeline (normalized Parquet input)
- Strategy runtime (intent emission)
- Risk gate (intent evaluation)
- Portfolio projection (fill application)
- Money types

## Error taxonomy

| Error | Classification | Recovery |
|---|---|---|
| Data gap (missing partition) | Operational | Skip; flag in results |
| Illegal state transition during replay | Terminal (bug or data) | Halt replay; preserve partial results |
| Fill model parameter out of range | Data-quality | Reject run configuration |

## Metrics

| Metric | Type | Labels |
|---|---|---|
| `replay.events_processed` | Counter | — |
| `replay.duration_seconds` | Histogram | — |
| `replay.fill_model` | Gauge | model (0=bar, 1=quote, 2=orderbook) |

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `replay.fill_model` | string | "bar_conservative" | Fill model to use |
| `replay.slippage_bps` | float | 0.5 | Slippage in basis points |
| `replay.commission_bps` | float | 1.0 | Commission in basis points |
| `replay.latency_ms` | integer | 10 | Simulated exchange latency |

## Replay decision trace validation

A replay run must reconstruct every DecisionTrace from the replayed event stream. The replayed trace must be byte-for-byte identical to the original trace for the same inputs:

- Every trace entry stage (MarketEventReceived through BrokerAcknowledgement) must be present in order.
- The correlation_id chain must link every entry from the originating event to its broker acknowledgement.
- Configuration digest and portfolio snapshot ID must be recorded and match the run configuration.

Trace entries are replayed from the same EventStore aggregate_type="DecisionTrace" records used in live operation.

## Performance budget

- Throughput: 1M events replayed in <15s (bar-conservative fill model)
- Determinism: 100% identical across runs
- See `PERFORMANCE_SPEC.md`.

## Failure behavior

See `FAILURE_MATRIX.md`:
- Replay failure (illegal state) → halt, preserve partial results
- Data gap → skip, flag in results
