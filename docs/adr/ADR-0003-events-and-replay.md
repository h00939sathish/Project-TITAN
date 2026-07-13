# ADR-0003: Canonical events, serialization, and replay scope

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Architecture Council
- **Decision scope:** Event schema, serialization format, event store, replay semantics
- **Supersedes / superseded by:** None

## Context

The event system is the foundation of auditability, recovery, and replay. Every economic fact is an immutable event. The format and store must support deterministic replay, schema evolution, and solo-developer simplicity.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §2: NautilusTrader's typed eventing pattern is the strongest reference; no speculative CQRS.
- `../SYSTEM_CONTRACTS.md`: defines the envelope, canonical commands/events, aggregate ownership.
- `../IDEAL_PLATFORM.md`: durable event log is the source of truth.
- `SPECIFICATIONS.md` (this project): VERSIONING.md defines the schema versioning policy.

## Decision

1. **Serialization: JSON with JSON Schema.** The canonical wire format is UTF-8 JSON with a published JSON Schema per `message_type` and `schema_version`. This is debuggable, language-independent, and trivially storable. Binary encodings (FlatBuffers, Cap'n Proto) are deferred until a measured profile shows JSON is a bottleneck.
2. **Event store: SQLite.** Append-only table keyed by `message_id` (UUID v7). Includes envelope JSON blob plus extracted columns for query (aggregate_id, message_type, occurred_at, schema_version). SQLite is file-based, zero-operations, and easily backed up. DuckDB is evaluated if analytical queries become a bottleneck.
3. **Replay: deterministic by-construction.** Replay reads events in `occurred_at` order and applies each to an aggregate. Matching input (data partitions, code digest, parameters, seed) produces identical output — verified by byte-for-byte comparison of the emitted event stream.
4. **Projections are rebuildable.** Portfolio, exposure, and PnL projections are derived from events. They are never the authoritative source for economic facts; the event log is.
5. **No speculative CQRS.** Separate read and write stores are introduced only when a measured latency or contention profile justifies it, with an ADR.

## Alternatives and trade-offs

- **Protobuf / FlatBuffers** — faster than JSON but adds schema compilation step and is harder to debug. Deferred to a future ADR when profiling shows JSON is the bottleneck.
- **DuckDB as primary store** — excellent for analytical queries but adds a dependency with less ecosystem maturity for transactional append-only patterns. SQLite first; DuckDB for replay analytics if needed.
- **Separate event store service (EventStoreDB, Kafka)** — premature distribution. Rejected for solo-developer stage.

## Consequences

- JSON parsing is a known cost on the hot path. Mitigated by doing heavy parsing at the adapter boundary and keeping the core path's internal types efficient.
- SQLite may become a bottleneck at very high write volumes (>50k events/s). Monitored and deferred.

## Validation and operations

- Event store throughput validated against PERFORMANCE_SPEC.md (50k events/s sequential append).
- Replay determinism validated by golden event streams in tests.
- Schema evolution validated by compatibility tests: old readers tolerate new optional fields; new readers tolerate old required fields.
- Rollback: any event store migration must have a forward and backward path.

## Approval

Architecture Council — 2026-07-13
