# Data Architecture

> **Owner:** Data Platform
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council; Data Governance Owner
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md)
> **Supersedes:** None
> **Review Frequency:** Quarterly; before a new data source or retention change

## Principles

Separate immutable source facts, reproducible derived datasets, operational state, and advisory knowledge. Every dataset has an owner, schema, lineage, license/classification, retention rule, quality checks, and access policy. The event/replay rationale is grounded in `../IDEAL_PLATFORM.md`; research reproducibility follows `../RESEARCH_PROTOCOL.md` through this suite.

## Stores and authority

| Store | Canonical content | Technology shape | Authority |
|---|---|---|---|
| Market-data lake | raw vendor files and normalized bars/ticks | immutable object storage, partitioned Parquet | historical/research data |
| Event store | ordered command outcomes and domain facts | append-only transactional store | operational fact history |
| Relational operational DB | configuration, registry, approvals, query projections | transactional relational store | current administrative state only |
| Feature store | versioned, point-in-time-correct derived features | Parquet/offline plus governed online cache if justified | feature definitions/artifacts |
| Experiment DB | hypotheses, runs, metrics, artifacts, lineage | relational metadata + immutable artifacts | research record |
| Vector DB | evidence-linked advisory chunks/embeddings | isolated retrieval store | advisory retrieval only |
| Cache hierarchy | reconstructed views, reference and market snapshots | bounded in-process/distributed cache | never canonical |

## Lake and Parquet layout

Raw data is retained unchanged under `lake/raw/source=<vendor>/dataset=<kind>/ingest_date=YYYY-MM-DD/`. Normalized Parquet is written to `lake/normalized/asset_class=<class>/venue=<venue>/instrument=<canonical_id>/date=YYYY-MM-DD/part-*.parquet`. Feature datasets use `lake/features/feature_set=<name>/feature_version=<semver>/as_of_date=YYYY-MM-DD/`. Every file carries schema id, producer digest, source checksum, event-time range, ingest-time, quality status, and corporate-action adjustment policy. Partition by query predicate, avoid tiny files, and preserve event-time ordering within write batches.

## Event and cache policy

The event store persists the envelope from `SYSTEM_CONTRACTS.md`, with monotonic aggregate revision and immutable retention. Snapshots accelerate recovery but are disposable, versioned derivatives. Cache levels are process-local for static/reference data, shared read-through for non-authoritative query views, and broker/data snapshots only with TTL, source timestamp, and staleness detection. A cache miss, eviction, or invalidation failure must cause a source read or safe rejection—not a guessed decision.

## Quality, lineage, and retention

Ingress validates schema, range, duplicates, monotonicity where applicable, timezone, currency, symbol mapping, and late/corrected data. Quarantine bad records with reason and source pointer. Derived data records its exact source partitions, transform code digest, parameters, and run id. Retain audit events, order/fill/risk decisions, approvals, and production experiment artifacts under the longest applicable legal and business policy; retain raw market data by license; expire caches aggressively; delete advisory embeddings/chunks according to source retention and user/contractual rights. Legal retention durations are configured policy, not hard-coded here.

## Recovery and access

Restore lake/object data from immutable replicated storage; rebuild projections/features from versioned sources; never rebuild an economic fact from a vector store or cache. Enforce least-privilege access by environment and data classification; production identities cannot write research history. See [SECURITY.md](SECURITY.md) for encryption, audit, and credential controls.

