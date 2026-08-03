# Governance Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Formalize the Research → Architecture → Implementation → Evolution continuous loops from OPERATING_PRINCIPLES.md as a specification and ADR.

**Architecture:** Two documents cross-referencing existing artifacts — no code changes. The ADR records the decision to adopt the loop structure; the SPEC defines the loop mechanics.

**Tech Stack:** Markdown.

## Global Constraints

- Do not create new governance concepts — codify what OPERATING_PRINCIPLES.md and AGENTS.md already describe.
- Cross-reference existing documents rather than duplicating them.
- Both documents are Accepted on creation (they codify existing practice, not propose new structure).

---

### Task 1: Write ADR-016 — governance loop adoption

**File:** `docs/adr/ADR-016-governance-loops.md`

ADR recording that TITAN operates four continuous loops:

1. **Research Loop** — generate evidence (hypotheses, backtests, data analysis)
2. **Architecture Loop** — review evidence, update ADRs, specs, and scope
3. **Implementation Loop** — build from accepted specs, test, verify
4. **Evolution Loop** — reflect on operations, identify gaps, trigger research

Each loop has: trigger, inputs, process, outputs, and exit gate. Cross-reference OPERATING_PRINCIPLES.md and AGENTS.md.

### Task 2: Write Governance.spec.md

**File:** `specifications/Governance.spec.md`

Formal spec for the governance loop system. Include:
- Purpose: ensure TITAN operates as a closed-loop learning system
- Boundary: owns the loop definitions and artifact lifecycle; delegates content to individual ADRs and specs
- Inputs: research artifacts, incident records, post-trade reflections, gap analyses
- Outputs: new/updated ADRs, new/updated specs, new plan documents
- State machine: Research → Architecture → Implementation → Evolution → Research (cycle)
- Metrics: loop cycle time, artifact age, stalled-plan count
- Configuration: max plan age before review, required approvers per loop

### Task 3: Update specifications/README.md

Add Governance.spec.md to the cross-cutting specs table.
