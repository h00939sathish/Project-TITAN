# Contracts

This directory references the machine-readable canonical contract schemas. The authoritative JSON Schema files live at `contracts/` in the repository root, where they can be imported for runtime validation and CI testing.

## Relationship between specifications/contracts and contracts/

| This directory | `contracts/` (repo root) |
|---|---|
| Human-readable specification | Machine-readable JSON Schema |
| Describes the contract's purpose, fields, and semantics | Enforces structure, types, and required fields |
| Updated when design decisions change | Updated in lockstep with implementation |
| References `contracts/*.schema.json` | CI-validated against implementation |

## Current contracts

| Spec doc | Machine schema | Status |
|---|---|---|
| TradeIntent.spec.md | contracts/trade-intent-v1.schema.json | Phase -1 |
| Risk.spec.md | contracts/risk-decision-v1.schema.json | Phase -1 |
| Order.spec.md | contracts/event-envelope-v1.schema.json | Phase -1 |

These are created during Phase B implementation. The schema JSON is the source of truth for wire format; this document is the source of truth for meaning and behavior.
