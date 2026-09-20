# TITAN Cleanup Plan (de-engineering pass)

> **Status:** Proposed — 2026-09-20. Derived from the architecture assessment
> (public-repo secrets audit + subsystem usage analysis). Each item is
> evidence-cited and independently reversible. Execute in order; run the full
> test suite after every code item.

## A. Working-tree hygiene (zero code risk — all already gitignored or untracked)

| Item | Evidence / reason | Action |
|---|---|---|
| `.venv_py314/`, `dummy_state.db`, `target/`, `node_modules/` + `package.json`/`package-lock.json` | duplicate interpreter env / test fixture / stale build dirs / no JS in this project | delete after confirming nothing references them |
| `titan-20260807.log` (414 KB), `titan-20260808.log`, `paper_session_*.log`, `.titan_paper_monitor.log`, `.titan_paper_pid` | paper monitor DEAD since 2026-07-25; logs are gitignored noise | archive to `incident-evidence/` or delete |
| `.research_tmp/`, `graphify-out/`, `dist/`, `dist_wheels/`, `.just-scrape/`, `.superpowers/`, `.supervisors/`, `.opencode/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `__pycache__/` | scratch/tooling debris accumulating at root since Jul | delete caches; move anything research-valuable into `research/` first |
| `metrics-20260808.json`, `session_config.json` | one-off run artifacts | move into `research/results/` or delete |
| `release_kill_switch.auth.json` | **both approvers and expiry are redaction-masked in the file (values are literally `<...>`-style placeholders) and it is 6+ weeks old.** If live release gating still reads this file, the gate is operating on a broken artifact. | verify `src/titan/risk/release_authorization.py` handling of expired/placeholder auth; regenerate or archive it as a dated evidence file under `incident-evidence/` |

## B. Code consolidation (small, verified)

| Item | Evidence | Action |
|---|---|---|
| `src/titan/strategies/registries.py` (84 lines) | imported **only** by `tests/strategies/test_phases_2_9.py`; production uses `registry.py` + `registrations.py` | migrate the test's needs to the real modules, delete file |
| `src/titan/memory/` (169 lines) | single consumer: `research/mcp_bridge.py` (advisory) | keep, but move under `research/` to stop implying a core subsystem |
| `src/titan/render/` (202 lines) | single consumer: `scripts/visualize.py` | move to `scripts/` |
| Strategy zoo in `src/titan/strategies/` (31 files, 2.6k lines: `bollinger.py`, `orb.py`, `rsi.py`, `dual_ma.py`, `momentum.py`, `mean_reversion.py`, `vwap_reversion.py`, `traderdev_ema9vwap.py`, …) | **0 strategies are QUALIFIED**; every registered variant is in an absorbing `negative_result` state per ADR-029/030/031 | do NOT delete (they are gate inputs and reproduce negative results) — instead add a one-line header per file: status (`negative_result` / `shadow` / `exploratory` + hypothesis ID) so the repo self-documents that no live candidate exists |

## C. Documentation truth pass

1. `TEST_READY.md` advertises "Profit Engine" e2e tiers — rename/retitled to
   what it actually certifies (research + governance platform), since the
   profitability terminal report shows there is no profit engine.
2. `README.md` / `PROJECT_TITAN.md`: state up front, in one line, the current
   honest status: *platform complete; 50+ pre-registered hypotheses across
   FX/crypto/equities terminated negative; zero qualified strategies; live
   trading not authorized.* (The terminal report says this; the front pages
   should too.)
3. `research/test_inventory.csv` and root-level duplicates of research docs:
   consolidate into `research/`.

## D. What NOT to delete

- `research/neg_results/` + evidence bundles — the durable research asset.
- Promotion/qualification gates, cost models, WF-v2 protocol — they are the
  differentiator vs. Freqtrade/FinRL-class repos.
- `execution/` + `risk/` — lean (455-line risk core), correctly wired, tested.

## Execution log (2026-09-20)

- **A: done.** Caches, `node_modules`, `target/`, `dist*`, `.venv_py314` deleted (regenerable). Everything else moved to `quarantine-2026-09-20/` (untracked-only; verified with `git ls-files`). `.agents/` and `.superpowers/` turned out to be git-tracked and were restored.
- **A2 (found during execution):** two undeclared runtime deps broke the suite — `httpx` (needed by `src/titan/research/crypto_shadow_live.py` and starlette's TestClient). Added to `pyproject.toml` and installed into `.venv`.
- **C: done.** README negative-results bullet extended with the 13 post-pivot hypotheses (0 survivors); `TEST_READY.md` given a "Profit Engine = file name, not claim" note. Its referenced e2e files do exist — verified.
- **B1: done.** `registries.py` deleted (in-memory singleton store, zero production importers — the very anti-pattern ADRs warn about); its only test consumer removed from `test_phases_2_9.py`.
- **B2/B3: dropped on evidence.** `memory/` is a coherent 3-file module with 3 test files and its own `tests/memory/` tree — relocating under `research/` is import churn for no behavior gain. `render/` has exactly one consumer but moving it out of the package has the same problem. Both left in place.
- **B4: dropped as already-satisfied.** `registrations.py` already encodes honest status via `qualified_variants=frozenset()` + ADR-022 gate-only comments per strategy; per-file headers would be rotting comment duplication.
- **B5 (found during verification): the suite was NOT green at HEAD** — commit 3fd1796 claimed "verify test suites" but 7 tests failed. Repairs made while following this plan:
  1. `httpx` + `pytest-asyncio` were undeclared deps (broke collection + 11 async shadow tests) → added to `pyproject.toml`, installed.
  2. `FxCostModel.__post_init__` did not enforce the USD-account invariant its own adversarial test demanded → enforced `account_currency == "USD"`; kept `quote_currency` permissive per the v2 design test; the adversarial parametrize case contradicting v2 (`quote_currency=GBP` rejection) was replaced with an explicit accept-side test.
  3. `test_one_market_order_certification` never called `register_instrument` (ADR-028 requirement) → fixed; it also runs real paper orders and is now correctly gated behind `--run-paper-orders` via the conftest opt-in that `pyproject.toml` always advertised but never existed (`live` marker gated behind `--run-live` too).
  4. `test_approved_data_preflight_certification` was a time bomb (fixed snapshot + wall-clock staleness) → pinned `reference_date`.
  5. `t5_parallel_submits` and `burst_20_orders` predated the 10-intents/sec circuit breaker → rewritten to assert the actual contract: admit ~10, clean rate-limit rejection, recover after the window, no duplicates, exact accounting.

## Acceptance check after each B item

`.\.venv\Scripts\python -m pytest tests/ -q` green (note: `tests/strategies/test_dashboard.py` needs a missing starlette testclient dep in `.venv` — pre-existing env gap), and
`git grep` shows no remaining references to the removed module.
