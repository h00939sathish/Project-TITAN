# CURRENT GITHUB COMPETITIVE MATRIX

**Date:** 2026-09-29. All activity evidence **observed today** by curling each repo's HTML page
plus `commits/HEAD.atom` and `releases.atom`, and by downloading + parsing source tarballs.
Stars are recorded but never used as a quality signal.

## Dimensions

| Dimension | TITAN | Reference capability | Evidence | Gap | Relevance |
|---|---|---|---|---|---|
| **Market data** | OHLCV daily+intraday via IBKR/Alpaca; FRED/ECB clients; **Dukascopy tick decoder**; **no tick/L2 producer in the runtime**; core datasets **absent from disk** | `Vibe-Trading` ships a measured FX spread table with provenance (`forex.py:37`: *"The XAU/USD figure is the median measured from Dukascopy tick data, 2017-2024 (~$0.32); the rest are typical retail quotes and should be overridden if you have better data"*) | TITAN `data/tws_feed.py:330`, `alpaca_feed.py:74,115`; Vibe `agent/backtest/engines/forex.py:25-40` | **Cost data provenance.** TITAN's costs are unsourced constants | **HIGH** — this is the EXP-00022 fix |
| **Research** | Hypothesis classes, preregs, evidence bundles, negative-results discipline — **all real artifacts** | `microsoft/RD-Agent` **v1.0.0 2026-09-23**, 133 open PRs — a real hypothesis→experiment→evaluate loop | TITAN `research/hypotheses/*-prereg.json`; RD-Agent repo | TITAN has the *format* but not a *loop* | MEDIUM |
| **Backtesting** | **6+ simulators**; long-only harness; 2× PnL double-count; `sqrt(252)` on bars | `nautilus_trader` `nautilus-execution/{matching_core, matching_engine}` — a real matching engine; 2.0.0rc5 **2026-09-15**, commits **2026-09-29** | `nautechsystems/nautilus_trader` | TITAN fakes fills; Nautilus models them | MEDIUM (TITAN is daily/4h, not microstructure) |
| **Replay** | `ReplayEngine` `backtest/engine.py:63`; determinism tests present | `nautilus-execution` `position_replay`; `hummingbot` | — | TITAN's replay is testable but untested against a broken harness | LOW |
| **WFO** | **FAKE** — `harness.py:383-412` does no training. The real `WalkForwardOptimizer` is called by **no experiment** | `Vibe-Trading` `quantlib/crossvalidation.py`: `purged_kfold_splits`, `group_purged_kfold_splits`, `purged_walk_forward_splits`, `combinatorial_purged_splits` (CPCV), `detect_boundary_leakage` | TITAN `harness.py:383-412`; Vibe `crossvalidation.py:451,524` | **CRITICAL** | **HIGHEST** |
| **Monte Carlo** | **ABSENT — 0 implementations anywhere** | `Vibe-Trading` factor costs + FX engine with swap/metals; `quantstats` v0.0.86 **2026-09-27** | grep across `src/`, `research/`, `scripts/`, `core/src/` → 0 files | **CRITICAL** | HIGH |
| **Optimization** | 198-cell EMA9×VWAP surface — **reports no significance statistic at all** (`sharpe_from_pnl` multiplies by a function that returns 1.0, and is never called) | `vectorbt` `deflated_sharpe_ratio` `returns/metrics.py:19`; `v1.1.1` **2026-09-26** (⚠️ open PRs #872/#873 fixing kurtosis convention bugs) | TITAN `ema9vwap_parameter_surface.py:69-84,96`; vectorbt `returns/metrics.py:19,nb.py:338-361` | **CRITICAL** | **HIGHEST** |
| **Strategy framework** | 10 registered; **6 crash on a daily feed**; `dual_ma`/`vwap_reversion` have **zero** test references | `freqtrade` **2026-09-29 05:23**, 54.9k★, ~401 contributors; `jesse` v3.2.3 **2026-09-27** | TITAN `registrations.py`; `bridge.py:110` | TITAN's registry is a list, not a framework | LOW — TITAN is not a retail-bot product |
| **Portfolio construction** | `hrp_allocator.py`, `rebalancing.py`, `factor_simulator.py` — **all dead code, zero prod importers** | `PyPortfolioOpt` v1.6.0; `vecportfolio` (not audited) | grep: no prod importer | Underbuilt | LOW now |
| **Risk** | **11-rule Rust gate, fail-closed, mutation-resistant.** Mutation M16 (bypass) and M12 (10× looser) **killed** | `lean/Algorithm.Framework/Risk`; `ai-hedge-fund` `risk/limits.py` (119 LOC + 95 test) | TITAN `core/src/risk.rs:273` | **TITAN is competitive or better** | — |
| **Execution** | Fill-price model; **no queue model, no latency model** | `nkaz001/hftbacktest` `src/backtest/models/queue.rs:1130` + **6 depth backends each with tests** (`btreemarketdepth.rs:444`, `fuse.rs:713`, `hashmap…:619`, `roivectorm…:805`) | TITAN `backtest/fills.py:24`; hftbacktest source | **Gap is real but low priority** — TITAN is not HFT | LOW |
| **Broker integration** | IBKR (real `ibapi`), Alpaca (real `alpaca-py`), Simulated, Fincept (**stub** — `fincept_native` import fails) | `nautilus-interactive-brokers` — **a real Rust crate**; 17 venue adapters in Nautilus; `lumibot` 435 test files | TITAN `ibkr_adapter.py:124`, `alpaca_adapter.py:52` | Nautilus's IBKR crate is a gift | MEDIUM |
| **Reconciliation** | `ReconciliationEngine.compare` (Rust) `reconciliation.rs:131`, called `engine.py:1372`; kill-switch on Critical | `lumibot` `docs/2026-01-19_IBKR_FUTURES_MESMOMENTUM_FIRST_DIVERGENCE_AUDIT.md`; `Vibe-Trading` `agent/src/live/runtime/reconcile.py` (608 LOC + 351 test) | — | TITAN's is real but **unverified in operation** | HIGH — read lumibot's audits |
| **Observability** | Prometheus exporter real; **15 of 25 metrics never written**; `cli.py:142` reads an always-zero counter and reports "Broker truth matches: YES" | `lumibot` dated engineering diary; `QuantDinger` `check_agent_billing_postgres.py` | TITAN `operations/export.py:79` | **Actively misleading** | HIGH |
| **Recovery** | Rust event store + WAL; **`cli.py:127` `TypeError`** — the recovery CLI is broken | `vibe-trading` reconcile | TITAN `restart.py:121` | **CRITICAL** — recovery is a success criterion | HIGH |
| **Paper trading** | `paper_session.py` — **crashes on first signal**; 0 orders placed ever | `lumibot`, `freqtrade`, `jesse`, `hummingbot` all run paper continuously | TITAN `paper_session.py:914` | **CRITICAL** | **HIGHEST** |
| **AI** | **172 LOC, 0.6%, zero LLM calls, dead** | `microsoft/RD-Agent` v1.0.0 **2026-09-23**; `microsoft/qlib` (commit 2026-09-16, release stale 13 months) | TITAN `src/titan/memory/`; `mcp_bridge.py:66` fabricates strategy names | TITAN has **nothing** here | LOW — see hype table |
| **Agent architecture** | `memory/` + `mcp_bridge.py`; fabricated returns | `RD-Agent`; `QuantConnect/mcp-server` (official, only **77★**) | — | — | LOW |
| **Memory** | `embedding_vector` populated **nowhere**; `search_similar_trades` can never match | Any vector store | `memory/vector_memory.py:84-97` | Spec'd, not built | **DELETE** |
| **Tool use** | None | `QuantDinger` `mcp_server/` (999 files, 315 test files) | — | — | LOW |
| **Performance** | Throughput gate `< 15.0s` in CI — real | `hftbacktest` `Accelerated Backtesting.ipynb`; `akquant` (Rust-accelerated, 251 test files) | `tests/test_throughput.py:62` | **NOT a bottleneck — TITAN is nowhere near CPU-bound** | **NONE** |
| **Testing** | 1180 pass / 17 skip; 85% line coverage; **0% effective coverage of metrics and strategy signals**; 92 Rust tests unreachable from pytest | `TradingAgents` — 84 of 204 files are tests (**41%**); `Vibe-Trading` 336-line leakage suite; `QuantDinger` 315 test files incl. Postgres idempotency | mutation testing, this audit | **CRITICAL** | **HIGHEST** |
| **Deployment** | Shell scripts with **hardcoded Windows paths** on a Linux checkout; `ruff` installed but never invoked; `mypy` `continue-on-error`; **CI never ran until `698cd7b`** | `lean` daily builds; `nautilus` release train | `supervise_paper_session.sh:8`, `ci.yml:44-46`, `tests/test_ci_workflow.py:47-56` | **CRITICAL** | HIGH |
| **Developer experience** | Strong specs, no `ruff`, no coverage floor, no mutation testing, 4 broken entrypoints, absent datasets | — | — | Data absent ⇒ **no research is reproducible** | **HIGHEST** |

## The three gaps that matter

1. **Statistical validation layer — entirely absent.** DSR, PSR, PBO, purged/CPCV, embargo.
   `Vibe-Trading/agent/src/quantlib/` has all of it with a 336-line leakage test suite.
   `vectorbt/returns/metrics.py:19` has DSR (⚠️ read open PRs #872/#873 first — the kurtosis
   convention bug silently inflates DSR). **This is an import, not a build.**
2. **Operational verification — the runtime has never run.** 0 paper trades, 0 orders, 6 broken
   entrypoints, 0 of 3 core datasets on disk. No amount of comparison substitutes for this.
3. **Absolute-value economic assertions — 1 test in 1180.** Mutation testing proves Sharpe and
   profit factor can be arbitrarily wrong with a green suite.

## Where TITAN is genuinely competitive

**The Rust core.** 11-rule fail-closed risk gate, `rust_decimal` ledger, WAL event store,
20-edge order state machine, reconciliation engine. Mutation testing could not break it;
a PnL sign-flip fails 35 tests. Against every project in the survey, TITAN's *kernel* is
peer-quality. The problem is entirely above the kernel.
