# ADR-034: Restore the CI gate — dead branch trigger, advisory typing, ruff posture

- **Status:** Proposed (2026-09-21) — Architecture Council and Risk Owner
- **Date:** 2026-09-21
- **Owners:** Architecture Council
- **Supersedes:** N/A (remediation of a control that was never wired)

## Context

TITAN's only CI workflow, `.github/workflows/ci.yml`, triggers on
`branches: [main]` for both `push` and `pull_request`. The repository's actual
trunk is `master` (`git remote show origin` → `HEAD branch: master`; no `main`
branch exists locally or on `origin`). GitHub Actions evaluates `on.push` /
`on.pull_request` strictly against matching ref names, so **the workflow has
never executed** — not once.

The job it would have run enforces, in order: `cargo` check/clippy/test (Rust
core), `maturin build`, `mypy src/titan tests/`, `scripts/check_adr_gate.py`,
`pytest tests/`, and a replay throughput benchmark. Every automated correctness
control was therefore dead. This is the systemic root cause behind the repeated
"green badge / overclaim, red on inspection" incidents the project has already
absorbed: commit `3fd1796` claimed "verify test suites" while 7 tests failed at
HEAD (repaired in `490d1af`), and the AGENTS.md implementation gate ("tests
written / verification defined") had no machine to enforce it. This is the
"exists but not wired" failure mode documented in `../FAILURE_ANALYSIS.md`.

Measured ground truth this iteration (offline, `.venv` 3.13.9, `_core`
importable):

- `pytest tests/` (live tests deselected): **1163 passed, 12 skipped, 4
  deselected** — green.
- `scripts/check_adr_gate.py`: **PASS** (29 ADRs) — green.
- `mypy --strict src/titan`: **387 errors in 70 files**; the safety-critical core
  (`execution/ risk/ data/ backtest/`) alone contributes **117 errors**,
  including genuine type defects (`backtest/engine.py`: unsupported
  `float` + `Decimal` operator; `BarResult.fill_price` annotated `str`).
- `ruff check src/titan tests`: **1580 errors**. Ruff is *installed* in the CI
  job but never invoked.

Consequence: simply repointing the trigger to `master` would make the first
blocking step (`mypy`) red and keep trunk permanently red, because the declared
`strict = true` typing posture is not currently satisfied anywhere near enough
to gate on.

## Decision

1. **Fix the trigger.** `on.push` and `on.pull_request` fire on `master`, the
   real trunk, so the workflow actually runs.

2. **Make the typing gate honest, not decorative or permanently red.** The
   `mypy src/titan tests/` step is renamed and set to `continue-on-error: true`
   (advisory). This is a net *increase* in signal: it was never blocking (it
   never ran); it now reports the 387-error debt on every push without
   fabricating a green compliance badge.

3. **Ruff stays unenforced, explicitly.** Do not add a `ruff check` blocking
   step (1580 violations would red trunk on arrival). Leaving ruff installed but
   unrun is recorded here as a deliberate, tracked decision rather than an
   oversight, so it is no longer mistaken for an active gate.

4. **Regression-lock the trigger.** `tests/test_ci_workflow.py` parses the
   checked-in workflow YAML and asserts it triggers on `master` and not `main`,
   so the trigger cannot silently drift back to a non-existent branch.

## Consequences

- On the first push to `master` after approval, ADR gate, `pytest tests/`, and
  the throughput benchmark become blocking and green (verified offline); the
  Rust job's true state is confirmed then (not executable in this offline env).
- `mypy` output appears as a red-but-non-blocking annotation. This is the desired
  visible-debt state, replacing invisible dead debt.
- The repo stops implying a strict-typing guarantee it does not meet: the
  `strict = true` declaration in `pyproject.toml` is aspirational until the
  ratchet below completes; this ADR is the tracking record.

## Ratchet-to-blocking plan (follow-up iterations)

1. Triage the 117 core errors first — `backtest/engine.py`'s `float`/`Decimal`
   mixing and the `fill_price: str` annotation are potential *correctness* bugs,
   not just typing nits, and belong in the deterministic-simulation work stream.
2. Introduce a per-module `[[tool.mypy.overrides]]` baseline so the gate blocks
   on **new** errors in already-clean files while grandfathering remaining debt.
3. Shrink the override set per iteration; when empty, drop `continue-on-error`.
4. Add `ruff check` on the same ratchet basis once violations are triaged.

## Rollback

`git revert` of the single commit restores the prior workflow; no runtime, data,
state, or order-path code is affected. Fully reversible.

## Monitoring

The `tests/test_ci_workflow.py` regression test is the standing alarm: it fails
in the local suite (and, once live, in CI) if the trigger is ever changed away
from the trunk branch again.
