# MarketEvent Specification

> **Owner:** Strategy Runtime
> **Status:** Active — Phase J (multi-timeframe)
> **Last Review:** 2026-07-24
> **Supersedes:** None
> **Implemented in:** `src/titan/runtime/events.py`

## Purpose

Define the canonical typed event envelope for all market and operational events entering the TITAN runtime. Every event — bar close, tick, heartbeat, broker fill, corporate action, news, economic release, or advisory proposal — enters through one versioned, traceable envelope.

## Boundary / Ownership

Owns: MarketEvent schema, provenance chain (message_id, causation_id, correlation_id), payload digest.

Called by: session runner (event ingress), RuntimeEvaluator (dispatch).

## Inputs

- Raw market data, broker callbacks, agent proposals, heartbeats, and system events normalized to the envelope.

## Outputs

- `MarketEvent` records to the event store and `RuntimeEvaluator.on_market_event()`.

## Envelope fields

| Field | Type | Description |
|---|---|---|
| `message_id` | `str` | Globally unique event identifier |
| `causation_id` | `str` | ID of the event that caused this one |
| `correlation_id` | `str` | End-to-end correlation ID across the decision path |
| `occurred_at` | `datetime` | Timestamp when the event occurred (source time) |
| `received_at` | `datetime` | Timestamp when the event was received by TITAN |
| `schema_version` | `int` | Envelope schema version (currently 1) |
| `source` | `str` | Originating system or component |
| `event_type` | `str` | One of: Tick, Quote, BarClosed, CorporateAction, EconomicRelease, News, Heartbeat, BrokerFill, AdvisoryProposal |
| `instrument_id` | `str` | Instrument identifier |
| `payload` | `dict` | Type-specific payload |
| `payload_digest` | `str` | SHA-256 digest of the canonical JSON payload |

## Accepted event types

- **Tick** — real-time trade tick
- **Quote** — quote update (bid/ask)
- **BarClosed** — closed bar at a supported timeframe
- **CorporateAction** — dividend, split, merger
- **EconomicRelease** — economic indicator release
- **News** — news headline or article
- **Heartbeat** — system health signal
- **BrokerFill** — fill notification from broker
- **AdvisoryProposal** — draft TradeProposal from an advisory/AI producer

## Error taxonomy

| Error | Classification | Recovery |
|---|---|---|
| Duplicate `message_id` | Data-quality | No-op; event skipped |
| Unknown `event_type` | Data-quality | No-op; event skipped |
| Missing required field | Data-quality | Reject at ingress |
| Payload digest mismatch | Security | Reject; alert |

## Metrics

- Events ingested per second
- Duplicate event rate
- Unknown event type rate
