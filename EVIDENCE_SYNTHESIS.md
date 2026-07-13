# R&D Evidence Synthesis and Traceability

> **Owner:** Architecture Council
> **Status:** Active — pre-implementation evidence baseline
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council; Risk Owner; Security Owner for license/credential decisions
> **Depends On:** All 15 R&D reports in `../`
> **Supersedes:** Informal cross-references in handbook v1.0
> **Review Frequency:** Before any implementation ADR; after material source correction

## Method and rule of precedence

This document synthesizes the sections of all supplied R&D reports into implementation implications. It distinguishes a pattern worth retaining from source code that is safe to adopt. Where reports conflict, direct correction/audit evidence wins over comparative scoring; the hostile review is a challenge record, not automatic adoption authority. No repository code is incorporated without license, maintenance, compatibility, security, and test evidence recorded in an ADR.

## 1. Repository catalog — `REPOSITORY_CATALOG.md`

The catalog classifies seven systems and their maturity, languages, licenses, live capability, tests, and unique strengths/weaknesses. NautilusTrader is the production-grade multi-asset execution reference; Jesse is the mature crypto research/indicator reference; Fincept is a commercial desktop connector/data reference; LLM_trader and TradingAgents are research-only AI references; TRADE is an academic pipeline; new trade is a pre-alpha event/risk reference. **Implication:** selection begins at subsystem level and every imported implementation remains subject to its stated maturity and license.

## 2. Architecture comparison — `ARCHITECTURE_COMPARISON.md`

The report compares architecture, functional behavior, and code quality for each repository. It supports a typed event-driven microkernel, adapter boundary, explicit state machine, replay/reconciliation, and separated research/execution paths. It also identifies anti-patterns: web monoliths, desktop-driven server design, direct composition-root coupling, god-class coordinators, and safety features disconnected from the hot path. **Implication:** TITAN’s `SYSTEM_CONTRACTS`, `EXECUTION_SPEC`, and `PROJECT_STRUCTURE` are mandatory boundaries; no source architecture is copied wholesale.

## 3. Performance comparison — `PERFORMANCE_COMPARISON.md`

NautilusTrader leads latency/throughput through a single-thread Rust/Tokio hot path but has a single-core ceiling, dual-stack complexity, and fragile interior-mutation assumptions. Jesse has strong backtest throughput with Rust kernels but a Python GIL-bound runtime. Fincept is performant for a desktop data terminal, not server-side execution; new trade has modest asyncio/event-bus throughput; LLM systems are seconds-to-minutes, cost/rate-limit bound. **Implication:** define real workload baselines before selecting a runtime; AI never belongs in a latency-sensitive route; “Rust-like” architecture does not require direct Rust/Cython code adoption.

## 4. Reliability comparison — `RELIABILITY_COMPARISON.md`

The report establishes non-negotiable operational behavior: durable recovery, idempotent ordering, broker reconnection, duplicate protection, reconciliation, and safe shutdown. NautilusTrader’s interval-based reconciliation and idempotency are the strongest reference; Fincept’s reconnect/data-stall handling and durable journal are valuable; Jesse lacks core reconciliation; research systems lack recovery; TRADE and new trade include critical safety mechanisms that are not wired or incomplete. **Implication:** implementation starts with durable facts, `UNKNOWN` order handling, reconciliation, and fail-closed recovery—not strategies or AI.

## 5. Risk-engine comparison — `RISK_ENGINE_COMPARISON.md`

NautilusTrader supplies the strongest production validation pipeline: typed denial reasons, price/quantity/notional/margin checks, throttling, and `ACTIVE`/`REDUCING`/`HALTED` states. New trade offers the broadest risk concepts—persistent kill switch, Kelly sizing, VaR, impact, margin, earnings filter, and optimizer—but its implementation quality is unsafe. TRADE supplies correlation-aware Monte Carlo VaR and anti-pyramiding ideas; Jesse has no centralized risk authority; TradingAgents’ LLM risk debate is qualitative and unacceptable for capital control. **Implication:** implement a deterministic core risk pipeline first; re-derive and test risk mathematics rather than importing pre-alpha code; LLM risk remains prohibited.

## 6. Strategy-engine comparison — `STRATEGY_ENGINE_COMPARISON.md`

NautilusTrader and Jesse jointly lead: the former for lifecycle, deterministic simulation, multi-asset semantics, and realistic OMS; the latter for indicator breadth, Optuna, Monte Carlo, significance testing, and ML gather/predict workflow. Other systems demonstrate either AI novelty without validation or strategy quantity without verified edge. Walk-forward and Monte Carlo are rare and must be first-class. **Implication:** strategy packages require typed versioning, reproducible parameter/data lineage, simulation, walk-forward, Monte Carlo, and paper evidence before any capital promotion.

## 7. AI-agent comparison — `AI_AGENT_COMPARISON.md`

LLM_trader provides the strongest bounded AI patterns: vector retrieval over prior evidence, deterministic reflection, falsification prompts, structured output, provider error classification, and computed overrides. TradingAgents contributes typed/stateful research orchestration and schema ideas but is expensive and incorrectly delegates risk to LLMs. Fincept demonstrates tool registry/auth-gate concepts but has excessive tool/provider breadth; TRADE’s regex parsing and weak prompt controls are rejected; new trade’s backtest-and-human mutation gate is useful but its LLM value is uncertain. **Implication:** apply `AI_GOVERNANCE`; cap providers/tools, enforce schemas/provenance/abstention, and place all AI behind deterministic validators with no economic authority.

## 8. Best-of-breed matrix — `BEST_OF_BREED_MATRIX.md`

Across architecture, performance, reliability, risk, execution, broker integration, observability, testing, deployment, and AI, the matrix confirms that no single repository wins all dimensions. NautilusTrader wins the core execution/reliability path; Jesse wins research primitives; Fincept informs broker breadth/reconnect and terminal-grade engineering; new trade informs risk/event concepts; LLM_trader informs advisory AI. The matrix also exposes missing observability and test depth in most alternatives. **Implication:** TITAN adopts evidence-backed interfaces and acceptance tests, not a “merge the winners” plan.

## 9. Failure analysis — `FAILURE_ANALYSIS.md`

This report is the hard safety gate. It identifies dual-codebase/build burden in NautilusTrader; missing centralized risk/reconciliation in Jesse; Fincept’s `UnifiedTrading` god object and SQLite event-path concern; LLM_trader’s lack of event sourcing/backtesting; TradingAgents’ LLM risk manager; TRADE’s secrets, unwired circuit breaker, no recovery, and negative alpha; and new trade’s unauthenticated control path, kill-switch race/auto-reset, key leakage, silent order failure, unwired reconnector, and stub adapters. Its cross-cutting finding is “exists but not wired.” **Implication:** never accept feature existence as evidence. Every control must have an end-to-end hot-path test, telemetry, failure injection, and recovery drill.

## 10. Adoption decisions — `ADOPTION_DECISIONS.md`

The decision record classifies components as adopt, modify, borrow, reference, or reject. Retain the underlying candidates: typed messages and microkernel/state/reconciliation concepts; Jesse validation and indicator interfaces; Fincept outbox/journal, registry, MCP auth, and data-stall patterns; LLM_trader memory/falsification/override patterns; TRADE’s VaR mathematics; and new trade’s risk breadth/event concepts. Reject direct use of unsafe defaults, LLM capital authority, source-specific god objects, regex output parsing, and premature complexity. **Qualification:** “Adopt Completely” in this report is not implementation authorization; the hostile review and license/compatibility findings require each decision to be ratified by ADR.

## 11. Ideal platform — `IDEAL_PLATFORM.md`

The target design describes execution, risk, broker, backtesting, strategy, observability, AI, configuration, testing, deployment, data, persistence, and API surfaces. Its strongest contribution is the intended separation of execution core, deterministic risk, connectors, validation, advisory AI, and operational controls. **Implication:** use it as a reference architecture and subsystem checklist. It is not a bill of materials: language, concurrency, data-model, and licensing mismatches prohibit surgical assembly of source repositories.

## 12. Implementation roadmap — `IMPLEMENTATION_ROADMAP.md`

The original phases sequence early core/indicator/CI work, then event store/risk/advisory AI/brokers, then CQRS/backtesting/portfolio/agent orchestration, with later research. Its phase gates correctly require event throughput, risk tests, paper adapters, research-live parity, reconciliation, and prolonged paper evidence. **Conflict resolved:** its 34–48 person-week estimate and early AI placement are overly optimistic. AI must follow deterministic contracts, risk, backtesting, and paper operation; a realistic plan includes integration and legal work explicitly.

## 13. Executive summary — `EXECUTIVE_SUMMARY.md`

The summary recommends a conditional go, subsystem synthesis, AI advisory only, avoidance of LLM risk/regex parsing/provider sprawl, and a small team. Its key condition—do not progress before stable core evidence, viable operating model, and positive paper evidence—remains valid. **Implication:** no live-capital roadmap may be inferred from this summary; it is a decision brief and must yield to detailed corrective reports.

## 14. Fincept delta report — `FINCEPT_DELTA_REPORT.md`

The upstream check corrects version, script count, local-only agent runtime, missing dependency, failed local builds, README divergence, and hardened CI facts. It verifies useful upstream concepts—bounded contexts, DataHub, broker registry, secure storage, CI/self-tests—but confirms that a desktop terminal is not TITAN’s server core. **Implication:** use upstream, not stale-fork claims; perform license and maintenance review; borrow connector/reconnect/event-journal patterns only through TITAN interfaces.

## 15. Hostile review — `HOSTILE_REVIEW.md`

The challenge report identifies the central planning flaw: the original synthesis assumes incompatible Rust, Python asyncio, Qt/C++, databases, and concurrency models are plug-compatible. It revises rankings and recommends treating source repositories as pattern sources, estimating integration at 50–70 person-weeks rather than 34–48, resolving LGPL/build implications first, and moving AI after backtesting. It also argues that TradingAgents schemas/provider abstraction and TRADE’s honest negative-alpha results have value even when their systems are unsuitable for production. **Implication:** before implementation, choose either a conservative single-core path or an ambitious clean-room path through ADRs; do not combine Path B scope with Path A schedule.

## Reconciled implementation baseline

1. **Architecture and code are distinct decisions.** TITAN may emulate a proven pattern but imports code only after legal, compatibility, security, ownership, and test review.
2. **Deterministic capital path first.** Contracts, event persistence, risk admission, order state/idempotency, broker truth, and reconciliation precede research automation, strategy breadth, or AI.
3. **Controls are end-to-end obligations.** A kill switch, circuit breaker, limit, broker adapter, and alert are incomplete until invoked in the real path and failure-tested.
4. **Research-to-live parity is a gate.** Backtest/paper/live share canonical contracts and preserve exact data, configuration, package, and decision lineage.
5. **AI is advisory and defeasible.** It may create typed research proposals; deterministic code validates, rejects, and records all consequential output.

## Required ADRs before implementation

| ADR | Decision required | Evidence that must be resolved |
|---|---|---|
| ADR-0002 | Initial runtime/core path and license posture | NautilusTrader LGPL/build/v2 concerns; conservative vs. clean-room path |
| ADR-0003 | Canonical serialization, event store, and replay scope | Nautilus/Fincept/new-trade differences; no speculative CQRS |
| ADR-0004 | Risk, halt, recovery, and reconciliation invariants | risk comparison and failure-analysis P0 controls |
| ADR-0005 | Backtest/paper execution fidelity | Jesse/Nautilus simulation evidence; calibration and parity gates |
| ADR-0006 | Broker certification and credential boundary | Fincept delta, broker patterns, security/reconnect/reconciliation evidence |
| ADR-0007 | AI advisory eligibility and tool/provider policy | AI comparison; no AI authority; measurable research-only value |

## Handbook consequence

The existing TITAN handbook is a policy and target-specification baseline. It must not be treated as an approved implementation design until the ADRs above resolve the contradictions surfaced here. Subsequent edits must link an exact source finding or ADR, name rejected alternatives, and add a test/operational acceptance criterion.

