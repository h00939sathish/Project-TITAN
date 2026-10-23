# TITAN PRESERVE — What Is Genuinely Good

**Date:** 2026-09-29. Every positive claim here has implementation evidence. Nothing is
preserved on the basis of a document, an ADR, or a test count.

## 1. THE RUST CORE — the single best asset in the repository

`core/src/` — 4,132 LOC, 2,882 non-test, 92 `#[test]` functions.

| Module | What it does | Why it's good |
|---|---|---|
| `risk.rs:273` | 11-rule deterministic gate, short-circuiting | **Mutation M16 (bypass) and M12 (10× looser) were KILLED.** It is genuinely wired to behaviour, not decorative |
| `portfolio.rs:103,171-221,267,311` | Position/cash/PnL ledger in `rust_decimal` | **A realized-PnL sign-flip injected across the whole suite failed 35 tests.** The money arithmetic is defended |
| `orders.rs:74` | 20-edge order state machine | **Mutation M15 (trailing-stop direction) KILLED.** Explicit transition table, not ad-hoc branching |
| `event_store.rs:25` | WAL SQLite + 4 indexes | Single-writer, durable, auditable. The right choice |
| `reconciliation.rs:131` | Drift detection at 5%/1% fractions | Wired at `engine.py:1372`; kill-switch on Critical `:1377-1385` |
| `lib.rs:20` | PyO3 seam, 33 types, no leakage | Clean boundary. No floats touch economic values |

**Why this matters more than anything else in the repo:** the audit found defects in the Python
research and runtime layers, and **none** in the kernel. `rust_decimal` for money, WAL for
durability, and an explicit transition table for order lifecycle are exactly right, and the
mutation results prove they were built, not just written.

**Preserve verbatim.** Do not "modernise" it. Do not add features to it. It is correct.

## 2. Fail-closed defaults

`core/src/risk.rs:450 load_or_default` → `Triggered` / `Halted` on an empty store.

**Verified empirically:** a fresh engine reports `trading_state=Halted kill_switch=Triggered
blocks_routing=True` both before and after `start()`. This is correct per ADR-020, and it is the
single most important safety property in the system.

**Preserve.** If anything in TITAN is right by design rather than by accident, it is this.

## 3. Circuit breakers — actually wired

`risk/circuit_breaker.py:54` — `record_intent` at `engine.py:996`, `record_error` at `:1131`,
`record_success` at `:1171`. **All three call sites present.** Limits: 10/s, 100/min, 3 errors.
`tests/risk/test_circuit_breaker_wired.py` exists.

**Preserve.** This is the counter-example to the project's own `PROJECT_TITAN.md:17` critique
of reference repos ("unwired circuit breakers"). TITAN wired them.

## 4. Fill absorption — single, idempotent delta path

`engine.py:638-739 _absorb_broker_fill`. Cumulative-quantity deltas; `delta <= 0` is a no-op
(`:658`); one path emits `PositionOpened/Changed/Closed` + `OrderFilled` (`:688-708`).
`tests/failure_matrix/test_duplicate_fill.py` exists.

**Preserve.** This is the correct answer to the "duplicate orders / duplicate fills" failure
class, and it is the design pattern the *research* harness should have copied (it did not — see
`harness.py:135-147`, where PnL is double-counted).

## 5. The research constitution and negative-results discipline

`docs/RESEARCH_CONSTITUTION.md`, `research/protocol_WF_v2_PRE_FROZEN.md`, `PIVOT_DECISION.md:24-27`:
pre-register hypotheses, freeze kill criteria, acquire data **before** backtesting, record every
result regardless of outcome, no post-hoc parameter tweaking.

**The intent is exactly right and it is unusual.** Several specific provisions deserve credit:

- `PIVOT_DECISION.md:25` — *"Use explicit spread/slippage/latency/commission assumptions."*
  Correct. The failure was in the constants, not the principle.
- `PIVOT_DECISION.md:44-46` — *"Short-term or single-window PnL spikes do not qualify as evidence."*
  This is precisely the flaw the evidence base then committed (12-month windows, n=1 screens).
- `PIVOT_DECISION.md:47-51` — required artifacts for any new program: charter, pre-registered
  gates, net-of-cost attribution, terminal report. The templates are good.
- The **negative-results library** as a first-class, committed artifact. Most projects discard
  nulls. TITAN kept them, with pre-registration text. That is why this audit was possible at all.

**Preserve the discipline. Fix the enforcement** — see `TITAN_STOP_BUILDING.md` §STOP #5.

## 6. The one genuinely sound negative result

**EXP-00016** — intraday FX momentum falsified. IC −0.0834, n = 12,384, bootstrap CI
[−0.102, −0.067], consistent across 3 temporal thirds and 2 pairs, opposite sign to the
hypothesis.

**This is a real, well-powered, correctly-analyzed negative result.** It is the correct outcome
for a falsified hypothesis and it should be kept as the reference standard for what a sound
TITAN conclusion looks like.

## 7. The self-diagnosis in EXP-00017's retest

`exp17_2fold_retest.py`'s own note is the most valuable sentence in the archive:

> *"The original EXP-17 'temporal' thirds were same-window sub-periods, NOT out-of-sample — so
> the effect was never OOS-validated before promotion."*

It also correctly identifies that the target (**forward |return|**) is **not a tradable signal** —
knowing the magnitude of the next move is not knowing its direction — and that the "cost check"
which passed subtracted a cost from a difference of mean **absolute** returns, which is not a
spread.

**This is a project that can find its own errors when pointed at them.** Preserve that. The
governance failed; the *instinct* is sound.

## 8. One well-powered rejection

**CRYPTO-006** (passive spread capture) — 4,872,006 fills, real Binance maker fee schedule,
measured edge **0.157 bps**. Rejected at its IS feasibility probe, a **probe-gated, not
absorbing, outcome** (a distinction the project explicitly tracks and is correct to track).

**Preserve the probe-gating concept.** Rejecting on a cheap feasibility probe *before* spending
a full OOS run is good economics and good statistics.

## 9. Pre-registration artifacts and the evidence-bundle format

`research/{crypto,equities,forex_research}/hypotheses/*-prereg.json` (15 files) with explicit
`pass_criteria`, plus `*-evidence-bundle.json` with manifest digests, cost breakdowns, quantile
returns, and regime breakdowns. EQ-002-core7's bundle contains a full cost attribution
(`total_borrow_cost`, `total_commissions`, `total_spread`, `total_friction`) and quantile
decomposition — **that level of artifact detail is genuinely good.**

**Preserve the format. Fix three things:** (a) thresholds must be **binding** — the code must
fail if a prereg key is missing, not default it (`equities_factor_screen_006.py:384-389`);
(b) preregs need a **timestamp** and must land in a commit *before* results; (c) `manifest_digest`
should cover the data, not just the universe.

## 10. `OPERATING_PRINCIPLES.md` and the governance intent

The *principles* are right and match what the evidence supports:
- "Disagree with evidence, make uncertainty visible, prefer deletion to accidental complexity."
- "Every production feature has an owner, runbook, metrics, failure test, rollback procedure,
  and retirement trigger."
- "AI may propose ideas, challenge questions. AI may not route orders, approve capital, or
  override risk controls" (`PIVOT_DECISION.md:40-41`).

**The principles are sound. The enforcement is not** — CI runs `check_adr_gate.py` (formatting)
and never runs `ruff` (installed, 1,593 violations) or `mypy` (continue-on-error, 2,368 errors,
with a test asserting it stays that way).

**Preserve the principles. Delete the apparatus that does not enforce them.**

## 11. `PROJECT_TITAN.md`'s architectural restraint

> *"a well-bounded deployable rather than premature microservices; process boundaries are
> introduced only when isolation, latency, scale, or ownership evidence justifies them."*

**This is correct and the project followed it** — no microservices, no message bus, no CQRS
projections ("The event log supports audit and recovery but does not justify speculative CQRS
projections"). Resist every future suggestion to add a service.

## 12. The CI decision not to enforce mypy — reconsider

ADR-034 makes mypy advisory. On a codebase with a `rust_decimal` core and a clean PyO3 seam,
2,368 type errors in 213 files is **not** worth fixing now, and blocking on it would stall the
real fixes. **The decision to make it advisory is correct.**

**But** `tests/test_ci_workflow.py:47-56` *asserts that it stays advisory*. That is a test
locking in the absence of a gate — remove the assertion, keep the advisory posture. And
**`ruff` must be enabled** — it is already installed, already failing, and 1,593 violations is
the cheapest available signal that the Python layer is under-disciplined.

## Summary of what to protect

| Preserve | Because |
|---|---|
| The Rust core, verbatim | Mutation-tested; the only code that survived hostile scrutiny |
| Fail-closed defaults | The most important safety property in the system |
| Circuit breakers | Actually wired, unlike the reference repos TITAN criticised |
| Idempotent fill absorption | The correct answer to duplicate-fill risk |
| Negative-results discipline | Unusual, valuable, and the reason this audit was possible |
| Pre-registration + evidence-bundle formats | Good artifacts; just need binding thresholds |
| EXP-00016 | A sound negative result, and the standard to hold others to |
| The self-diagnosis instinct | The governance failed; the instinct is sound |
| Non-microservice architecture | Correct restraint; resist future pressure to undo it |
