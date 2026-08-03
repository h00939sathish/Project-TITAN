# TITAN Architecture Decision Record — ADR-001

> **Title:** Generation 1 Completion & Generation 2 Transition  
> **Status:** Accepted  
> **Date:** 2026-07-30  
> **Decision Authority:** Architecture Council & Chief Research Architect  

---

## Context

Project TITAN began as a trading engine and evolved through governed execution platform into a hypothesis-driven quantitative research operating system. Over the course of Generation 1, the following subsystems reached architectural maturity:

| Domain | Status |
|---|---|
| Data & Research Infrastructure | ✅ Mature |
| Experimentation Framework | ✅ Mature |
| Statistical Governance | ✅ Mature |
| Evidence Management | ✅ Mature |
| Replication Framework | ✅ Mature |
| Portfolio Evaluation | ✅ Mature |
| Research Process Governance | ✅ Mature |
| Scientific Knowledge Management | ✅ Mature |

## Decision

**Generation 1 (Platform Construction) is officially complete.**

The platform has established a stable constitutional framework for quantitative research, including governance, statistical standards, replication policy, portfolio evaluation, and institutional knowledge management. Future progress is expected to come primarily from the discovery and validation of economically grounded hypotheses rather than additional infrastructure.

**Generation 2 (Alpha Discovery Program) begins immediately**, where success will be determined by the quality, reproducibility, and portfolio relevance of the evidence produced.

## Architecture Freeze

All infrastructure enumerated in Research Constitution §3 is frozen behind the ADR Requirement Gate. No modification is permitted without a new ADR demonstrating an explicit, unresolvable research bottleneck.

## G3 Transition Criteria

Generation 3 will **not** be defined by elapsed time. G3 begins only when TITAN reaches a qualitative change in capability — specifically, when the platform can consistently generate and validate new hypotheses faster or more effectively because of the knowledge accumulated during G2, not because of additional framework engineering. Until that threshold is crossed, G2 remains the appropriate focus.

## Future Review Cadence

Architecture reviews should become infrequent. The primary artifacts worth reviewing are:

- Experiment designs & preregistrations
- Evidence bundles
- Replication results
- Research journals
- EQI dimension scores
- Annual retrospectives

If the constitution is doing its job, those artifacts — not the codebase — will become the principal record of TITAN's progress.

## G2 Benchmark Questions

At the end of Generation 2, the review should ask:

1. Which economic mechanisms consistently survived replication?
2. Which assumptions about markets were proven false?
3. Which findings improved portfolio construction?
4. Which hypotheses changed the way future research is conducted?
5. Which pieces of evidence would still be convincing if reviewed independently?

## Consequences

- The 1:10 engineering-to-research ratio guideline is now active.
- Sprint success is measured by Definition of Done (Constitution §2), not code output.
- Research Review Boards (Constitution §4) replace implementation milestone reviews.
- The four G2 risks (Data Quality, Economic Validity, Execution Realism, Model Decay) are continuously monitored.

## References

- [Research Operating Constitution v1.0](RESEARCH_CONSTITUTION.md)
- [Canonical Research Questions](CANONICAL_RESEARCH_QUESTIONS.md)
- [Research Journal Template](../research/journal/TEMPLATE.md)
- [AGENTS.md](../AGENTS.md)
- [OPERATING_PRINCIPLES.md](../OPERATING_PRINCIPLES.md)
