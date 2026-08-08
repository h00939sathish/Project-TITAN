# Research Protocol

> **Owner:** Quantitative Research Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Research Owner; Risk Owner for promotion policy
> **Depends On:** [AI_GOVERNANCE.md](AI_GOVERNANCE.md), [TESTING_STANDARD.md](TESTING_STANDARD.md)
> **Supersedes:** None
> **Review Frequency:** Per methodology change; quarterly otherwise

## Purpose and scope

Research creates evidence; it does not authorize capital. This protocol governs repository study, market hypotheses, model-assisted analysis, benchmarks, strategy experiments, and architecture selection. It operationalizes the R&D approach in `../REPOSITORY_CATALOG.md`, comparison reports, and `../HOSTILE_REVIEW.md`.

## Research record

Each experiment has an immutable identifier and records: question; hypothesis; prior evidence; data sources and licenses; code and environment digests; parameters; time boundaries; expected falsifiers; results; limitations; reviewer; and promotion decision. Preserve raw inputs and generated artifacts enough to reproduce the conclusion.

## Evidence grading

| Grade | Meaning | Permitted use |
|---|---|---|
| A | reproducible production/replay evidence with independent review | informs controlled promotion |
| B | reproducible simulation, benchmark, or source-code analysis | informs implementation and paper testing |
| C | credible paper, vendor documentation, or bounded observation | hypothesis input only |
| D | anecdote, model output, popularity, or unverified claim | may motivate search; never a decision |

## Method

1. Frame a falsifiable question and declare the decision it could influence.
2. Inspect primary source, code path, tests, and operational evidence; distinguish feature existence from wired behavior.
3. Establish a baseline and fixed dataset/time split before tuning.
4. Run deterministic experiments with recorded seeds, costs, latency assumptions, survivorship controls, and data-quality checks.
5. Challenge the result using adverse regimes, ablation, alternative parameters, and counter-hypotheses.
6. Publish the record, limitations, and recommendation; create an ADR only when a durable architectural choice is proposed.

## Strategy and model research

AI may retrieve knowledge, generate candidates, and create falsification questions. Outputs must be structured, provenance-tagged, validated, and independently tested. Use walk-forward validation, Monte Carlo, replay, and paper trading before promotion, reflecting the selected Jesse validation strengths in `../STRATEGY_ENGINE_COMPARISON.md`. Do not use LLM confidence, debate consensus, or narrative plausibility as a risk metric.

## Promotion and knowledge management

Promote an experiment only when it is reproducible, statistically and operationally credible, survives predeclared falsifiers, has known failure modes, and meets the gates in `TESTING_STANDARD.md` and `IMPLEMENTATION_PLAYBOOK.md`. Retain rejected results with reasons to prevent repeated work. Advisory vector memory stores evidence pointers and expiry/retention metadata; it is never a source of trading truth.
