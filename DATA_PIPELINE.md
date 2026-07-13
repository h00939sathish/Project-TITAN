# Data Pipeline

> **Owner:** Data Platform
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Data Governance Owner
> **Depends On:** [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md), [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [RESEARCH_ENGINE.md](RESEARCH_ENGINE.md)
> **Supersedes:** None
> **Review Frequency:** Per source/schema change; quarterly otherwise

## Flow

`Source acquisition → immutable landing → schema/quality validation → canonical normalization → publication → feature generation → consumer freshness monitoring → correction/replay`. Every stage emits lineage and quality status; no downstream stage treats unvalidated data as tradable truth. This separates operational flow from store design and follows the reliability lessons in `../RELIABILITY_COMPARISON.md`.

## Ingestion and normalization

Connectors acquire vendor/exchange/broker files or streams with source timestamp, sequence/cursor, checksum, license, and entitlement metadata. Landing stores raw bytes immutably. Normalization maps provider identifiers to canonical instruments, UTC event/receive times, fixed-decimal price/size, currency, venue, condition flags, and schema version. Deduplicate by source identity/sequence; retain corrections as new facts with lineage rather than overwriting prior records.

## Quality gates

Validate schema, required fields, time ordering/coverage, duplicate rate, price/size ranges, crossed/locked quote rules where relevant, symbol/currency/precision mapping, corporate-action consistency, calendar validity, and freshness. Each batch receives `accepted`, `quarantined`, or `rejected` status plus reason codes and metrics. Critical stale, incomplete, or anomalous inputs are withheld from live consumers and trigger alerts; quality overrides are versioned, reviewed, and auditable.

## Publication and features

Publish only canonical, versioned datasets with partition manifest, quality status, source/transform digests, and change/correction notice. Consumers specify an as-of time and minimum quality/freshness requirement. Feature jobs are point-in-time correct, versioned, idempotent, and linked to source partitions and transform code. Backfills replay through the same normalized contracts and never silently change a prior experiment or production decision.

## Operations

Monitor lag, missing partitions, quarantine rate, correction volume, source health, feature freshness, and downstream consumption. Reprocess from immutable landing with a new run id; preserve original output and publish a supersession record. Access, retention, encryption, and deletion obey [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) and [SECURITY.md](SECURITY.md).

