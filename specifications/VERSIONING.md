# Versioning Policy

> **Owner:** Core Platform Architecture
> **Status:** Active — Phase -1 baseline
> **Last Review:** 2026-07-13
> **Decision Authority:** Architecture Council

## Principles

1. Every versionable artifact has a single, immutable version identifier at the time of creation.
2. Versions are independent — a strategy package version is unrelated to an event schema version.
3. Backward compatibility is deliberate, not accidental.
4. A compatibility break requires a new major version and an ADR.

## Artifacts and version schemes

| Artifact | Format | Example | Breaking change |
|---|---|---|---|
| Message schema | `major.minor` | `1.3` | Field removed, type changed, enum variant removed, semantics changed |
| Event contract | `major.minor` | `2.1` | Event meaning changed, required field added to existing major |
| Strategy package | `semver` | `1.4.2` (package-level) | Parameter schema change, data requirement change, signal semantics change |
| Configuration | Content-addressed SHA256 | `a1b2c3d4...` | Any change |
| Model prompt | `major.minor` | `3.0` | Tool set change, safety instruction change, output schema change |
| Broker adapter | `major.minor` | `2.0` | API version change, order semantics change, credential model change |
| Data contract | `major.minor` | `1.5` | Column removed, precision changed, normalization rule changed |

## Compatibility rules

- **Major version X** — consumers written for version X may consume version X.Y (any minor) but NOT version X-1 or X+1.
- **Minor version Y** — adds optional fields or new enum variants only. Required fields, existing enum meanings, units, precision, and semantic behavior never change within a major.
- A consumer that receives an unrecognized major version must reject, quarantine, and alert. It must never silently coerce or drop unrecognized required fields.

## Deprecation procedure

1. Publish a new major version.
2. Support the old major for at least one release cycle (or period specified in the owning ADR).
3. All consumers are migrated before the old major is retired.
4. A retired schema version is never re-used.

## Event store versioning

Events are stored with their original schema version. Replay replays them in their original format. A projection that needs to consume multiple schema versions applies explicit upgrade functions registered in a migration registry. No event bytes are ever mutated in place.
