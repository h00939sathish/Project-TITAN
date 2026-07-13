# ADR-0001: Specification-first implementation discipline

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Architecture Council
- **Decision scope:** All subsystems, all contributors
- **Supersedes / superseded by:** None

## Context

The handbook's central finding from `FAILURE_ANALYSIS.md` is that features are declared but not wired, and controls are instantiated but not tested. Specification-first discipline prevents this by requiring every subsystem to be fully specified (interface, state machines, errors, metrics, configuration) before a single line of implementation code is written.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §3: "Controls are end-to-end obligations"
- `../FAILURE_ANALYSIS.md`: "exists but not wired" is the most frequent cross-cutting failure mode
- `../HOSTILE_REVIEW.md`: identifies the gap between documented design and implementable specification

## Decision

No subsystem or cross-cutting change may be implemented until its `.spec.md` is written and accepted. A task is created only after its specification passes review. This applies to code and to configuration, deployment, and operational procedures.

## Alternatives and trade-offs

- **Waterfall risk** — specification-first could slow early iteration. Mitigated by keeping specs concise (not exhaustive design documents), by writing specs in the same session as the first implementation task, and by treating specs as living documents updated with ADRs.
- **Spec-first by convention only** — weaker than a hard gate. Rejected because the handbook's own evidence shows convention without enforcement produces unwired controls.
- **No spec requirement** — status quo. Rejected because it produced the failure modes documented in the R&D reports.

## Consequences

- Front-loaded specification effort (Phase -1). Trade-off accepted: saves time downstream by preventing rework, integration surprises, and untested controls.
- Specs must be maintained as the system evolves. ADRs record every material change to a spec.

## Validation and operations

- The PLAN.md checklist verifies spec existence before each implementation phase.
- CI checks that specs exist for every subsystem with open tasks (manual for Phase -1, automated in future).
- Rollback: a spec change that introduces an error is corrected via a new ADR; the implementation is adjusted to match.

## Approval

Architecture Council — 2026-07-13
