# TradeIntent Specification

> **Owner:** Strategy Runtime
> **Status:** Active — Phase -1
> **Last Review:** 2026-07-13
> **Supersedes:** None
> **Implemented in:** Phase B (core/src/messages.rs)

## Purpose

Define the canonical typed intent that a strategy may emit. TradeIntent is the only message type that bridges strategy logic and deterministic risk. It is never a broker order.

## Boundary / Ownership

Owns: TradeIntent schema, validation rules, provenance chain.
Delegates to: Risk gate (evaluation).
Called by: Strategy runtime, Research engine (advisory proposals only).

## Inputs

- Strategy package digest, parameter snapshot, and market/feature state

## Outputs

- `TradeIntent` messages to the risk gate
- `TradeIntentExpired` events (when an intent's time-to-live elapses without a decision)

## State machine

```mermaid
stateDiagram-v2
  [*] --> PROPOSED: strategy emits
  PROPOSED --> PENDING: accepted by risk ingress
  PROPOSED --> STALE: data became stale before evaluation
  PENDING --> ACCEPTED: risk decision = accepted
  PENDING --> REJECTED: risk decision = rejected
  PENDING --> EXPIRED: TTL elapsed before decision
  ACCEPTED --> [*]: consumed by execution
  REJECTED --> [*]
  STALE --> [*]
  EXPIRED --> [*]
```

## Dependencies

- Money types (price, quantity)
- Strategy package digest (validated package identity)

## Error taxonomy

| Error | Classification | Recovery |
|---|---|---|
| Missing required field | Data-quality | Reject at ingress |
| Invalid strategy digest | Security | Reject; alert |
| Stale market data reference | Operational | Reject; strategy must retry with fresh data |
| Expired intent | Operational | No-op; caller must submit new intent |
| Duplicate intent idempotency key | Operational | No-op (if same payload) or error (if different) |

## Metrics

| Metric | Type | Labels |
|---|---|---|
| `intent.proposed` | Counter | strategy_id |
| `intent.accepted` | Counter | strategy_id |
| `intent.rejected` | Counter | strategy_id, reason_code |
| `intent.expired` | Counter | strategy_id |

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `intent.default_ttl` | duration | 5s | Default time-to-live for an intent |
| `intent.max_ttl` | duration | 60s | Maximum allowed TTL |

## Performance budget

- Validation: p99 <5 μs
- See `PERFORMANCE_SPEC.md` (validation is part of risk-gate budget).

## Failure behavior

Stale data and expired intent are normal operational outcomes, not errors. See `FAILURE_MATRIX.md`.
