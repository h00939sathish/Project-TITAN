# Spot Metal Specification

> **Owner:** Core Platform Architecture
> **Status:** Accepted
> **Last Review:** 2026-07-20
> **Supersedes:** None
> **Implemented in:** Phase — (not yet implemented)

## Purpose

Define a spot-metal instrument type (one troy ounce of gold quoted in USD) for deterministic simulation and backtest. Not for live or paper-adapter execution.

## Boundary / Ownership

- Owns: `Commodity` contract type definition, spot-metal instrument factory, spot-metal calendar, data normalization acceptance.
- Delegates to: Portfolio engine (USD cash/PnL accounting), risk gate (position limits, gross exposure), execution engine (instrument registration via `submit_intent`).
- Called by: Strategy research harness, backtest scripts, simulated adapter.

## Inputs

- `{"symbol": "XAUUSD", "date": "...", "open": "...", "high": "...", "low": "...", "close": "..."}` OHLC CSV/JSON rows
- `TradeIntent{instrument_id="XAUUSD", ...}` from research harness

## Outputs

- `Instrument` with `ContractType::Commodity`, `InstrumentId("XAUUSD", "SPOT")`, step_size=1, tick_size="0.01", multiplier="1.0", currency="USD", precision=2
- `BacktestResult` with deterministic flat round-trip (buy 1 oz, sell 1 oz, zero position, USD PnL)

## State machine

None — instrument is immutable. The order state machine is already defined in Order.spec.md.

## Commands

- `RegisterInstrument("XAUUSD", instrument)` — allowed only on simulated/backtest adapters
- `submit_intent(TradeIntent{instrument_id="XAUUSD"})` — rejected when instrument not registered, or when routed through AlpacaAdapter

## Events

- `InstrumentRegistered(instrument_id="XAUUSD", contract_type="Commodity")`
- `InstrumentRejected(instrument_id="XAUUSD", reason="not registered")`
- `InstrumentRejected(instrument_id="XAUUSD", reason="commodity not supported by adapter")`

## Dependencies

- `core/src/types.rs` for `ContractType::Commodity`
- `titan.data.normalize` for symbol acceptance
- `titan.execution.engine` for registration check
- `titan.execution.backtest_adapter` for execution
- `titan.execution.simulated_adapter` for execution

## Error taxonomy

| Error | Classification | Recovery |
|---|---|---|
| Instrument not registered | Operational | Reject intent before adapter routing |
| Commodity on AlpacaAdapter | Operational | Reject at adapter boundary |
| Opening sell | Operational | Reject with "short not supported" |
| Price not tick-aligned | Data-quality | Reject at instrument validation |
| Stale price (> N ms) | Operational | Reject at data-freshness check within risk gate |
| Unknown symbol in data | Data-quality | Quarantine record in data pipeline |

## Metrics

| Name | Type | Labels | Description |
|---|---|---|---|
| `spot_metal.intents_total` | Counter | instrument_id, accepted | Total intents submitted for spot metal |
| `spot_metal.rejections_total` | Counter | instrument_id, reason | Total intents rejected for spot metal |
| `spot_metal.positions_ounces` | Gauge | instrument_id | Current open position in troy ounces |

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `spot_metal.allowed_symbols` | list[string] | ["XAUUSD"] | Symbols registered as spot-metal contracts |
| `spot_metal.max_position_ounces` | integer | 100 | Maximum open position (risk config companion) |

## Performance budget

Same as equities — p99 <1ms for intent validation, p99 <10ms for fill.

## Failure behavior

An unregistered instrument intent is rejected before any adapter call — the system fails closed. A spot-metal intent arriving at AlpacaAdapter is rejected at the adapter boundary. All failures are logged and counted in `spot_metal.rejections_total`. See FAILURE_MATRIX.md.
