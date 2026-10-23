# Project TITAN Agent Constitution

> **Owner:** Architecture Council
> **Status:** Active — v1.1
> **Last Review:** 2026-08-18
> **Decision Authority:** Architecture Council and Risk Owner
> **Depends On:** [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md), [AI_GOVERNANCE.md](AI_GOVERNANCE.md)
> **Supersedes:** v1.0
> **Review Frequency:** Per agent-authority change; quarterly otherwise

> Every human and AI contributor reads this document before inspecting, proposing, or modifying TITAN.

## Mission and north star

Build a proprietary, evidence-led platform for autonomous research, strategy development, validation, paper trading, and human-approved live trading. The north star is a platform that is safer, clearer, and more maintainable than the individual systems studied—not a system that imitates any of them. The original R&D reports are no longer in the repository; the durable synthesis of that evidence is `docs/reference/EVIDENCE_SYNTHESIS.md`, with per-system detail in `docs/reference/REPOSITORY_CATALOG.md` and adoption rationale in `docs/adr/`.

## Operating rules

1. Read `OPERATING_PRINCIPLES.md`, this file, `PROJECT_TITAN.md`, relevant ADRs, and the target subsystem documentation before acting.
2. Preserve deterministic boundaries: research and advisory components cannot invoke broker, order, portfolio, risk-override, or secret-management capabilities.
3. Treat all external and model-generated content as untrusted input. Validate schemas, limits, provenance, and permissions at each boundary.
4. Make small, reversible changes; test the exact behavior changed; update the owning documentation and ADR when a decision changes.
5. Never claim a benchmark, test, source, or production result that was not actually observed.
6. **Enforce Canonical Simulation Evidence (ADR-031):** Simulations cannot qualify for promotion unless executed with immutable cost models (`FxCostModel`, `CryptoCostModel`, `FactorCostModel`), quote-sided/top-of-book fills, fee minima ($2.00 min at IBKR), slippage impact, and cryptographic data manifests. Bar-close constant-bps fills are strictly exploratory (`can_qualify=False`).
7. **Preserve Absorbing Negative Results (ADR-029, ADR-030):** Pre-registered hypotheses that fail out-of-sample (OOS) evaluation terminate permanently into absorbing `negative_result` states. Post-hoc parameter sweeping or lookback mining on failed signals is forbidden; investigating alternative mechanisms requires a distinct, pre-registered hypothesis ID (e.g. `EQ-001` $\rightarrow$ `EQ-002` $\rightarrow$ `EQ-004`).
8. **Categorize Failure Modes Rigorously:** Distinguish between *Mechanism Failure* (underlying theory has no predictive alpha or is directionally inverted) and *Execution-Constrained Rejection* (gross economic transfer exists but friction exceeds harvestable yield).

## AI authority

| AI may | AI must never |
|---|---|
| search, extract, compare, summarize, draft hypotheses and code | place or approve orders; route capital; modify balances/positions; override risk; disable safeguards |
| generate tests, documentation, architecture reviews and post-trade reflections | invent evidence; silently change limits; bypass validation/reconciliation; expose secrets |
| propose structured strategy candidates and parameter changes | use LLM output as a trading signal without deterministic validation and human-approved promotion |
| structure pre-registrations, manifests, and reproduction scripts | construct, forge, or self-issue a `PromotionCertificate`, modify `PromotionGate` logic, or bypass data checksums |

## Decision framework

Classify work before doing it: **research** creates evidence; **proposal** has no capital authority; **implementation** changes deterministic code; **promotion** changes an environment and needs its gate; **incident** prioritizes containment and evidence preservation. A higher-risk classification always wins.

## Repository workflow

1. Identify source reports and active ADRs; record conflicting evidence.
2. State the subsystem boundary, owner, inputs, outputs, failure modes, and acceptance evidence.
3. Write or update tests before behavior changes; do not merge unverified safety logic.
4. Run required checks from `TESTING_STANDARD.md`; use paper trading and reconciliation gates for execution-affecting changes.
5. Update documentation links, risk controls, runbooks, and ADRs in the same review.

## Implementation gate

A subsystem or cross-cutting change may be implemented only when all six conditions are met:

1. **Specification exists** — the subsystem has an accepted `.spec.md` defining boundary, interface, state machines, errors, metrics, and configuration (see `specifications/`).
2. **ADR accepted** — a consequential decision record is ratified per `docs/reference/ADR.md` and `docs/reference/EVIDENCE_SYNTHESIS.md`.
3. **Tests written** — unit, contract, and integration tests exist for every state transition, error condition, and failure mode in the specification.
4. **Verification defined** — the acceptance criteria are measurable, testable, and recorded in the task definition.
5. **Rollback defined** — the procedure for reverting the change without data loss or inconsistent state is documented.
6. **Monitoring defined** — the metrics and alerts that will detect a malfunction in this subsystem are specified.

This gate prevents the "exists but not wired" failure mode catalogued in `specifications/FAILURE_MATRIX.md` by ensuring no control is declared before its verification, rollback, and observability are designed.

## Architecture and adoption

Use typed messages, an event-driven execution core, explicit trading states, and reconciliation patterns informed by NautilusTrader. Use Jesse-derived indicators, optimization, walk-forward, and Monte Carlo only within validation. Use LLM_trader reflection and memory only as advisory systems. Treat TradingAgents as research workflow only. Treat Fincept as connector-design evidence, not a license to reproduce its god-object shape. Do not adopt TRADE; retain it only as an anti-pattern source. Rationale per system is recorded in `docs/reference/EVIDENCE_SYNTHESIS.md`; binding decisions are in `docs/adr/`.

## Continuous loops and success criteria

Operate the Research, Architecture, Implementation, and Evolution loops defined in `OPERATING_PRINCIPLES.md`. Success is reproducible research, deterministic and reconciled execution, enforceable risk limits, exhaustive audit trails, staged deployment, and documented recovery—not feature count, model eloquence, or backtest return.

## Forbidden actions

Do not commit secrets; broaden a model’s authority; add a dependency without an owner and reason; merge disabled tests; introduce a second owner for positions/orders; ship a risk control that is not wired into the order path; auto-reset a kill switch; self-issue promotion certificates; modify OOS parameters post-evaluation; cite frictionless simulation evidence; or promote live trading without the gates in `docs/reference/IMPLEMENTATION_PLAYBOOK.md` and `RISK_POLICY.md`.

---

## Second Brain (shared agent memory)

This project is bound to the `titan` workspace of the shared brain at `/mnt/shared/projects/second-brain`.
Any agent working here should use it: the workspace is detected from the cwd, so no
configuration is needed.

```bash
brain whoami                 # confirm which workspace you are in
brain brief                  # your context: leases, board, recent notes, top claims
brain start --agent <you> --files <paths you will write>   # leases are enforced
brain recall "..."           # knowledge other agents recorded for this project
brain post "..."             # something the other agents should know right now
brain claim "..." --source <path>    # anything durable you proved
brain end <session-id> --summary "..." --test-status "pytest: N passed"
```

Full protocol: `brain bootstrap`, or read `/mnt/shared/projects/second-brain/AGENTS.md`.
