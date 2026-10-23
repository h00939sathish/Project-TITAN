# TRENDING TRADING PROJECTS — 2025/2026 Cohort

**Date:** 2026-09-29. Every claim below was verified by curling the repo page, the commit
Atom feed, the release Atom feed, and by **downloading and parsing the source tarball**.
Stars are recorded for context and used as *evidence of a mismatch*, never as quality.

## Verified activity table

| Project | URL | Last commit (observed) | Latest release | ★ | Contributors |
|---|---|---|---|---|---|
| **TradingAgents** | https://github.com/TauricResearch/TradingAgents | **2026-09-29** | v0.5.2, **2026-09-29** | **109,163** | **~24** ⚠️ |
| **ai-hedge-fund** | https://github.com/virattt/ai-hedge-fund | 2026-09-26 | 2.4.1, 2026-09-25 | 63,789 | — |
| **Vibe-Trading** | https://github.com/HKUDS/Vibe-Trading | **2026-09-29 07:38** | v0.1.15, 2026-09-09 | 34,276 | **~175** |
| **FinceptTerminal** | https://github.com/Fincept-Corporation/FinceptTerminal | 2026-09-19 | v4.5.0, 2026-09-01 | 32,079 | — |
| **QuantDinger** | https://github.com/OpenByteInc/QuantDinger | 2026-09-28 | v5.4.6, 2026-09-28 | 12,299 | — |
| **FinGPT** | https://github.com/AI4Finance-Foundation/FinGPT | 2026-09-23 | v1.0.0, 2026-04-08 | 21,301 | — |
| **FinRL** | https://github.com/AI4Finance-Foundation/FinRL | 2026-09-28 | v0.3.8, 2026-03-20 | 16,420 | ~137 |
| **RD-Agent** | https://github.com/microsoft/RD-Agent | 2026-09-23 | **v1.0.0, 2026-09-23** | 14,795 | — |
| **akquant** | https://github.com/akfamily/akquant | 2026-09-28 | v0.3.65 | 2,376 | — |
| **NQ0 / nof0** | https://github.com/wquguru/nof0 | 2025-12-07 | **none** | 2,750 | — |
| **QC MCP server** | https://github.com/QuantConnect/mcp-server | 2026-05-07 | 2025-08-22 | **77** | — |
| **prediction-market-backtesting** | https://github.com/evan-kolberg/prediction-market-backtesting | 2026-05-16 | none | 1,210 | — |
| **qsx-strategy-score** | https://github.com/jianweiweng05/qsx-strategy-score | 2026-07-27 | v0.3.4 | 983 | — |

## 🟢 REAL TECHNICAL ADVANCEMENT

### 1. `HKUDS/Vibe-Trading` — the highest substance-to-star ratio in the survey
**34,276★ / ~175 contributors.** 2,618 files, ~484k LOC Python, **836 test files**.
v0.x (v0.1.15) despite 34k★ — the version number is honest, the star count is not.

Verified in source:
- `agent/src/quantlib/multipletesting.py` — a from-scratch implementation of the entire
  Bailey/López de Prado toolkit: `sharpe_ratio`, `probabilistic_sharpe_ratio`,
  `expected_maximum_sharpe(n_trials, trial_sharpe_std)`, `deflated_sharpe_ratio`,
  `benjamini_hochberg`, `probability_of_backtest_overfitting`, with
  `DeflatedSharpeResult` / `FDRResult` / `CSCVResult` dataclasses.
- `agent/src/quantlib/crossvalidation.py` — `purged_kfold_splits`,
  `group_purged_kfold_splits`, `purged_walk_forward_splits`, `combinatorial_purged_splits`
  (CPCV), `_apply_purge_and_embargo`, `detect_boundary_leakage`, `LeakageReport`.
- `agent/tests/quantlib/test_crossvalidation.py` (336+ lines) — this is the strongest evidence
  in the entire survey that the code is real:
  ```
  test_a_naive_split_leaks_and_the_purged_split_does_not
  test_purging_removes_exactly_the_overlapping_observations
  test_embargo_removes_observations_after_the_test_block
  test_detect_boundary_leakage_flags_a_missing_embargo
  test_combinatorial_yields_every_combination
  test_every_observation_is_tested_exactly_once_across_kfold
  ```
  That is a maintainer who understands leakage, not someone who copied a library.
- `agent/backtest/engines/forex.py` (174 + 334 test), `agent/backtest/factor_costs.py` (416 + 303),
  `agent/src/live/runtime/reconcile.py` (608 + 351),
  `agent/backtest/binance_account_reconciliation.py` (437 + 333).

**Verdict: REAL. TITAN's single highest-leverage import.** Caveat: heavy LLM-agent coupling
makes it heavy as a dependency — vendor `quantlib/`, do not adopt the app.

### 2. `OpenByteInc/QuantDinger` — genuinely a system
999 files, ~254k LOC Python, **315 test files**, 74 doc files. `v5.4.6` shipping the same day
as commits. Test filenames prove it is not a wrapper:
```
test_account_reconciliation.py          test_account_mirror_for_strategy.py
test_account_snapshot_gate_orders.py    check_agent_billing_postgres.py
check_agent_idempotency_postgres.py     check_alpaca_ownership_postgres.py
order_fill_contracts.json               position_contracts.json
```
Postgres-backed integration checks for agent billing and idempotency, plus machine-readable
order/position contracts. **Verdict: REAL, and underrated.** Reconciliation + order contracts is
precisely TITAN's execution layer.

### 3. `microsoft/RD-Agent` — the real answer to "AI research agent"
**v1.0.0 on 2026-09-23**, 133 open PRs, institutionally backed. Solves the **R&D loop**
(hypothesis → experiment → evaluate), not signal generation. Qlib integrates it
(`docs/_static/img/rdagent_logo.png` in the Qlib tree).
**Verdict: REAL, and the correct AI reference for TITAN — which is a research loop problem,
not a "make the LLM emit BUY/SELL" problem.**

### 4. `akfamily/akquant` — Rust-accelerated, and nobody talks about it
796 files, ~133k LOC Python + **~35k LOC Rust**, **251 test files**. Created after 2025-01-01,
already v0.3.65, shipping on merge (`v0.3.65` is literally titled
*"Merge pull request #406"*). Same team as `akshare`.
**Verdict: REAL and underrated** — Rust-accelerated Python backtesting without Nautilus's
complexity. Not needed by TITAN (TITAN is nowhere near CPU-bound) but it is the right answer
to "do we need Rust."

## 🟡 REAL CODE, MISLEADING FRAMING

### 5. `TauricResearch/TradingAgents` — 109,163★, ~24 contributors
**~4,550 stars per contributor — the most extreme ratio measured in this survey.**

The code is *better than its reputation deserves*: 204 files, ~29k LOC, and **84 of those files
are tests (41%)**. `tradingagents/backtest.py` (214 lines) + `tests/test_backtest.py` (306).
But the backtest is a **rating sweep**: iterate tickers × dates, run the LangGraph agent,
settle forward returns, report hit rate. **No portfolio, no positions, no cash ledger** — the
Portfolio Manager emits a `BUY/HOLD/SELL` rating, not an order. No walk-forward, no Monte
Carlo, no risk engine, no reconciliation.

Creditable: `test_a_run_id_cannot_escape_the_results_directory` (path traversal) and
`test_summary_states_what_it_cannot_prove` (asserts the summary says "not archived" and
"sample" — they deliberately surface the small-n problem). **Good discipline.**

**Verdict: real code, educational artifact, NOT a research platform.**
**TITAN should steal the testing culture (41% test density, security-minded path tests) and
nothing else.**

⚠️ **Security:** at least four scam mirrors exist, e.g. `Tauric-Research-Trading/TradingAgents`
(22★, created 2026-04-30, 3 commits, description *"**Download** TradingAgents"). Verify you are
on `TauricResearch/TradingAgents`.

### 6. `virattt/ai-hedge-fund` — 63,789★, ~15k LOC
Substantially rebuilt since its demo days: `backtesting/engine.py` (299 + 509 test),
`event_study/` (413 + 213), `risk/limits.py` (119 + 95), `portfolio/construction.py` (103 + 162),
`pipeline/` (436 test), `llm/client.py` (365 + **614** test), `signals/` (Graham, Buffett,
Munger, Lynch, Druckenmiller, PEAD), plus a 2,165-line Textual TUI.
But **~15k LOC against 63,789★.** The "hedge fund" is 7 LLM personas emitting signals.
**Verdict: real code, demo scale, heavily hyped.**

### 7. `HKUDS/AI-Trader` — 22,624★, last commit **2026-06-11**, no releases
Three and a half months stale with 22k★ and 45 open issues. 149 files, ~32k LOC, **21 test
files**. Architecture is a **competition/tournament harness** — experiments, leaderboard,
challenges, participant schemas. **No backtest engine, no reconciliation, no IBKR**
(1 keyword hit, in a `SKILL.md`). **Verdict: stale and mis-scoped.**

### 8. `microsoft/qlib` + `FinRL` — real, but read the labels
Qlib: commit 2026-09-16, but **last release v0.9.7 is 2025-08-15 — 13 months stale**;
**177 open PRs** (largest backlog in the survey). The AI-oriented pipeline data→model→backtest
is genuinely implemented; the release cadence has decoupled from development.
**FinRL is NOT an LLM project** — grepped: `finrl/agents/{elegantrl, fasttd3, stablebaselines3,
rllib}`, i.e. classical RL. **Anyone citing FinRL as an "AI/LLM trading agent" is misinformed.**

### 9. `nkaz001/hftbacktest` — real but stale
Last commit **2025-12-23** (~9 months). rust-v0.9.4 / py-v2.4.4 on 2025-12-10. 4,792★.
Only 1 Python test file — but Rust `#[cfg(test)]` modules are extensive and were verified:
`backtest/mod.rs:1142`, `models/queue.rs:1130`, `btreemarketdepth.rs:444`, `fuse.rs:713`,
`hashmapmarketdepth.rs:619`, `roivectormarketdepth.rs:805` — **6 depth backends, each tested**,
plus a dedicated queue model. `connector/` (31 files) and `collector/` (15 files) are a real
data pipeline. **Verdict: real, treat as an algorithm reference, not a dependency.**

## 🔴 HYPE

- **`wquguru/nof0`** (2,750★, Go) — last commit 2025-12-07, **no releases**, 9 months stale.
  "AI trading arena." Source not audited; flag as unverified/likely-demo.
- **`FinGPT`** — v1.0.0 (2026-04-08) framed as *"Open-Source Financial AI **Platform**"*,
  21,301★. Activity verified, **code depth not audited** — treat the "platform" label as
  unverified.
- **`CloddsBot`** (2,900★), **`LangAlpha`** (1,786★) — active in 2026, source not audited.
  Not enough evidence to call either way.

## 🔬 Notable niche find

**`evan-kolberg/prediction-market-backtesting`** (1,210★) — *"An extension for Nautilus Trader."*
It extends the best engine in the survey into a new asset class. Small (last commit 2026-05-16,
no releases) but architecturally pointed: **it proves Nautilus's adapter abstraction is genuinely
portable.** That is the design lesson.

**`jianweiweng05/qsx-strategy-score`** (983★, created 2025) — *"Detect overfitting, weak edge,
drawdown risk, and random-timing luck from returns, equity curves."* Math **not** verified
against Bailey et al. But the existence of a standalone tool for this is itself evidence the
concern has gone mainstream. **Use as a cross-check, never as the gate.**

## The trend, honestly assessed

**REAL ADVANCEMENT** is in **statistical rigour** (Vibe-Trading's `quantlib`, vectorbt's DSR)
and in **the R&D loop** (RD-Agent). Both are *infrastructure for thinking*, not trading signals.

**HYPE** is concentrated in **LLM agent personas** — TradingAgents (4,550★/contributor, no
portfolio), ai-hedge-fund (7 personas, 15k LOC), AI-Trader (tournament harness, stale).
**Not one of them has a walk-forward engine, a Monte Carlo, a risk engine, or reconciliation.**

**Conclusion for TITAN:** the 2025-26 wave did **not** discover trading edge. It produced
(a) a mature statistical toolbox TITAN should adopt wholesale, and (b) a very loud
demonstration that LLM personas do not constitute a trading research platform. TITAN's
diagnosis of LLM risk control (`PROJECT_TITAN.md:17`) was correct, and the ecosystem has
vindicated it.

**The single highest-value trend finding for TITAN:** `Vibe-Trading/agent/src/quantlib/` is a
**drop-in replacement for the entire missing statistical layer**, with a 336-line leakage test
suite. It is an import, not a build.
