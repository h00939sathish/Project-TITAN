# ADR-016: Adopt four continuous governance loops

- **Status:** Accepted
- **Date:** 2026-07-20
- **Owners:** Architecture Council
- **Decision scope:** Governance loop definitions, artifact lifecycle, and decision authority across all TITAN subsystems
- **Supersedes / superseded by:** None

## Context

TITAN's operating principles define four continuous loops — Research, Architecture, Implementation, Evolution — in `OPERATING_PRINCIPLES.md:28`. The agent constitution in `AGENTS.md:62` requires all contributors to operate these loops, and the decision framework (`AGENTS.md:33`) classifies work by which loop it belongs to. However, the loops were never formally recorded as an ADR or specification, leaving their triggers, inputs, outputs, and exit gates implicit. Without a recorded decision, new contributors must rediscover the loop semantics from prose spread across two documents, and there is no authoritative artifact to reference in downstream specs.

## Evidence

- `OPERATING_PRINCIPLES.md:28-35` — defines each loop's permanent cycle and required output.
- `AGENTS.md:62-64` — establishes the loops as the operating model and defines success criteria.
- `AGENTS.md:33-35` — decision framework classifies work by loop (research → proposal → implementation → promotion → incident).
- `AGENTS.md:45-56` — implementation gate (six conditions) is the concrete exit gate of the Implementation loop.
- Existing ADRs (ADR-0001 through ADR-015) are Architecture-loop outputs; existing specs are Implementation-loop inputs.

## Decision

1. TITAN operates exactly four continuous loops in sequence:

   - **Research Loop** — generate evidence. Trigger: open question, gap analysis, or evolution-loop hypothesis. Inputs: data sources, evolution hypotheses, incident records. Process: observe → source → challenge → experiment → retain (per `OPERATING_PRINCIPLES.md:32`). Outputs: evidence record, reproducible result. Exit gate: evidence is peer-reviewed and stored in the R&D evidence base.

   - **Architecture Loop** — review evidence and update governance artifacts. Trigger: new evidence record, incident lessons, or scheduled review. Inputs: evidence records, current ADRs, current specs. Process: measure → review complexity/reliability → decide → retire (per `OPERATING_PRINCIPLES.md:33`). Outputs: new/updated ADR, explicit no-change decision. Exit gate: ADR is Accepted per `ADR.md` policy.

   - **Implementation Loop** — build from accepted specs. Trigger: accepted ADR with a spec change. Inputs: spec, ADR, implementation gate checklist. Process: design → test → review → paper trade → release (per `OPERATING_PRINCIPLES.md:34`). Outputs: tested, observable, reversible increment. Exit gate: all six conditions of `AGENTS.md:47-55` are met.

   - **Evolution Loop** — reflect on operations and identify gaps. Trigger: deployment, incident resolution, post-trade analysis, or periodic review. Inputs: production facts, reconciliation reports, trade logs. Process: collect production facts → reconcile → reflect → improve (per `OPERATING_PRINCIPLES.md:35`). Outputs: ranked improvement hypothesis, gap analysis. Exit gate: hypothesis is filed as a research task for the Research Loop.

2. The cycle repeats: Evolution → Research → Architecture → Implementation → (deployment) → Evolution.

3. Cross-referencing takes precedence over duplication. Each loop is defined in this ADR by its trigger, inputs, process, outputs, and exit gate. Details of the process steps belong to `OPERATING_PRINCIPLES.md` and `AGENTS.md`.

4. The Implementation Gate (`AGENTS.md:45-56`) is the mandatory exit gate of the Implementation loop and is not bypassed.

## Alternatives and trade-offs

- **Keep loops unwritten** — Rejected. Implicit structure creates ambiguity for new contributors and prevents formal cross-referencing from specs.
- **Define loops only in code (type-level loop enum)** — Rejected. Governance is a human-process concern; encoding it in types before process maturity creates coupling without benefit.
- **Merge all four loops into a single "governance" loop** — Rejected. The separation enforces the evidence → decision → build → reflect sequence; merging would collapse distinct quality gates.
- **Add a fifth "Incident" loop** — Deferred. Incidents follow the decision framework (`AGENTS.md:33`) as a higher-risk classification that short-circuits to containment. If incident frequency justifies a dedicated loop, a superseding ADR can add it.

## Consequences

- The four-loop structure is now the authoritative governance model, referenced from all future ADRs and specs.
- `Governance.spec.md` in `specifications/` provides the machine-readable state machine, metrics, and configuration for the loop system.
- Loop cycle time becomes a measurable metric (time from Evolution hypothesis to deployed implementation), enabling governance latency to be tracked.
- No existing artifacts change; this codifies current practice.

## Validation and operations

- This ADR is self-validating: its acceptance and referencing in the Governance spec prove the Architecture loop produced an ADR as output.
- Metrics: `governance.loop.research.cycle_time`, `governance.loop.architecture.cycle_time`, `governance.loop.implementation.cycle_time`, `governance.loop.evolution.cycle_time`, `governance.artifact.age_days`, `governance.stalled_plans`.
- Rollback: revert the ADR status to Rejected, remove the Governance spec reference from `specifications/README.md`. No code changes required.
- Retirement trigger: a superseding ADR that reorganizes the governance structure.

## Approval

Architecture Council — 2026-07-20
