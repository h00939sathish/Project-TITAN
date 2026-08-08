# System Contracts

> **Owner:** Core Platform Architecture
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council; Risk Owner for risk-state contracts
> **Depends On:** [ARCHITECTURE.md](ARCHITECTURE.md), [ADR.md](ADR.md), [RISK_POLICY.md](RISK_POLICY.md)
> **Supersedes:** None
> **Review Frequency:** Per schema change; quarterly otherwise

## Purpose

This is TITAN’s canonical contract authority for commands, events, aggregate ownership, serialization, and compatibility. An implementation may add a private type, but it may not alter a public contract without an ADR, versioning plan, and consumer evidence. Typed eventing, durable facts, and state ownership derive from the selected architecture in `../ADOPTION_DECISIONS.md` and `../IDEAL_PLATFORM.md`.

## Envelope

Every command and event is an immutable, schema-validated envelope:

```json
{
  "message_id": "uuid", "message_type": "order.submitted",
  "schema_version": 1, "occurred_at": "RFC-3339 UTC",
  "correlation_id": "uuid", "causation_id": "uuid|null",
  "aggregate_type": "order", "aggregate_id": "client_order_id",
  "source": "execution", "payload": {}, "metadata": {"config_digest":"sha256"}
}
```

`message_id` is globally unique; `correlation_id` follows a decision end to end; `causation_id` identifies the direct predecessor. Producers write UTC timestamps and never mutate an emitted message. Consumers deduplicate by `message_id` and must be safe under at-least-once delivery.

## Canonical commands and events

| Aggregate / owner | Commands | Events |
|---|---|---|
| Strategy package / Validation | `RegisterStrategyPackage`, `ApproveStrategyPackage`, `RetireStrategyPackage` | `StrategyPackageRegistered`, `StrategyPackageApproved`, `StrategyPackageRetired` |
| Trade intent / Strategy runtime | `ProposeTradeIntent` | `TradeIntentProposed`, `TradeIntentExpired` |
| Risk decision / Risk engine | `EvaluateTradeIntent`, `ActivateKillSwitch`, `ReleaseHalt` | `RiskDecisionRecorded`, `LimitBreached`, `KillSwitchActivated`, `TradingStateChanged` |
| Order / Execution engine | `SubmitApprovedOrder`, `CancelOrder`, `ReplaceOrder` | `OrderValidated`, `OrderSubmitted`, `OrderAcknowledged`, `OrderPartiallyFilled`, `OrderFilled`, `OrderRejected`, `OrderCancelled`, `OrderExpired` |
| Portfolio / Portfolio engine | `ApplyFill`, `ApplyCorporateAction` | `PositionChanged`, `BalanceChanged`, `ExposureChanged`, `PnLCalculated` |
| Reconciliation / Reconciliation engine | `ReconcileBrokerSnapshot`, `ResolveDiscrepancy` | `BrokerSnapshotReceived`, `ReconciliationStarted`, `ReconciliationDriftDetected`, `ReconciliationCompleted` |

Commands express requested work and may be rejected. Events express facts that occurred. Commands carry an idempotency key; an accepted execution command uses the client order id as its stable economic identity. A request may never be represented as an event or vice versa.

## Aggregate ownership

Only the named owner writes its aggregate: Strategy runtime owns candidate intent; Risk owns the risk decision and trading-state transition; Execution owns order lifecycle; Portfolio owns internal positions/PnL; Broker adapter owns external translation only; Reconciliation owns discrepancy lifecycle. The event store is canonical for facts, not a shared mutable object. Projections are read models and cannot authorize an order or repair truth.

## Required payload rules

An executable intent contains strategy-package digest, account, instrument identity, side, quantity/notional, order instruction, time-in-force, limit/stop values when applicable, expiry, market-data timestamp, risk-profile version, and provenance. `RiskDecisionRecorded` includes accepted/rejected result, ordered reason codes, every evaluated rule/version, inputs digest, limit snapshot, and expiry. Order/fill events include broker identifiers, client id, execution quantity/price/fee/currency, event-time and receive-time. Money and quantity use fixed decimal representation with explicit currency/precision; floats are forbidden for economic values.

## Serialization and evolution

Canonical wire format is UTF-8 JSON with a published JSON Schema per `message_type` and `schema_version`; binary encodings may be introduced only behind the same logical schema. Field names are `snake_case`. Unknown optional fields are ignored by tolerant readers; required fields, enum meanings, units, precision, and semantic behavior never change in place. Add an optional field in a minor-compatible version; publish a new major schema for a removal, changed meaning, precision/unit, or authority change. Producers do not emit a new schema until all declared critical consumers are compatible. Store original envelope bytes and schema version for replay.

## Compatibility and failure policy

Schema registry validation runs at producer, ingress, and consumer boundaries. An unrecognized command, invalid envelope, incompatible major version, missing required risk data, or illegal aggregate transition is rejected, quarantined with the correlation id, and alerted; it is never coerced into an economic action. A failed projection is rebuildable from facts. Contract changes require golden fixtures, backward/forward compatibility tests, replay evidence, migration/rollback plan, and an ADR.

