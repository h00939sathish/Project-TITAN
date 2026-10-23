# CURRENT RUNTIME MAP — Project TITAN (2026-09-29)

How the system ACTUALLY runs today, hop by hop, vs. what the documentation claims.
Evidence = file:line read from the working tree. Confidence: CONFIRMED (code read / reproduced), LIKELY (multiple corroborating files), HYPOTHESIS (single-source inference).

---

## 0. Executive map

```
                ┌──────────────────────────────────────────────────────────────┐
                │  DOCUMENTED ARCHITECTURE (README/ARCHITECTURE/ADRs)          │
                │  data → features → strategy → risk(Rust) → cert → execution  │
                │  → broker → fill → portfolio(Rust) → PnL → reconciliation    │
                │  → research feedback                                          │
                └──────────────────────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
 RESEARCH HARNESS              REPLAYENGINE                  PAPER SESSION
 (works end-to-end)            (broken: cert gate)           (broken: no session
                                                             init + cert gate)
 data.ingest → quality →       engine → PaperTradingEngine   paper_session.py → engine
 corporate_actions →           → submit_intent → CRASH      → submit_intent → CRASH
 StrategyRunner (next-bar      (engine.py:886-895)          (engine.py:886-895)
 fills, costs) → result                                            ▲
 NO risk, NO Rust, NO          tests pass only via           NO initialize_new_session
 portfolio, NO reconcil.       conftest.py:76-85 monkeypatch (risk gate restores HALTED)
```

Three disjoint paths exist. They share almost nothing. Only one works. The working one
contains none of the risk/portfolio/reconciliation machinery; the paths that contain it
are broken before any order is placed.

---

## 1. Path A — Research backtest harness (THE ONE THAT WORKS)

Entry: `scripts/backtest_strategies.py:122-202` (+ `backtest_per_timeframe.py`, `backtest_all_strategies.py`, `qualification_pipeline.py`)

| Hop | Code | What actually happens | Evidence |
|---|---|---|---|
| Data load | `data/ingest.py:13` | `read_csv` of local CSVs | backtest_strategies.py:71 |
| Validation | `data/quality.py:37` | `validate_and_quarantine(..., pass_through_unknown=True)` | backtest_strategies.py:71 |
| Adjustments | `backtest/corporate_actions.py` | common adjustments (`adjust_bars`) | backtest_strategies.py:72-73 |
| Features | none separate | indicators live INSIDE strategy classes; `titan.research.features` and `titan.runtime.feature_graph` are dead in production (imported only by tests) | harness.py:26-33 |
| Signal | `research/harness.py:194-225` | `make_*_signal_fn` factories → `StrategyRunner.run()` (harness.py:85-169) | |
| Sizing | `strategies/sizing.py` | `Sizer.size` | harness.py |
| Fill | `backtest/fills.py` | `BarConservativeFillModel.fill` — next-bar execution ("Execute pending signal from previous bar against current bar", harness.py:98) | harness.py:97-161 |
| Costs | fills.py:27, 100-104 | slippage 0.5 bps + commission 1.0 bps defaults (legacy path); FxCostModel for FX variants | |
| Risk | **NONE** | no RiskGate, no Rust, no certificates | (grep: absent from harness) |
| Portfolio/PnL | harness.py:89-167 | in-loop Python floats (`cash`, `position`, `equity_curve`) | |
| Metrics | `backtest/results.py` | `BacktestResult.compute` | |
| Persistence | `research/db.py:11-12` | SQLite `research_data/titan_research.db` — **directory does not exist in the repo** | qualification_pipeline.py |
| Tests | tests/research/test_harness.py | 3 tests; no test covers the scripts themselves | |

**Status: IMPLEMENTED and runnable, but it is a separate, simpler system** — no Rust core,
no portfolio engine, no reconciliation, no research feedback into trading. Its documented
outcome: 0 surviving strategies.

## 2. Path B — Engine-based backtest (ReplayEngine) — BROKEN

Entry: `research/run_exp20_strategy.py`, `research/replay_traderdev_ema9vwap.py`, `scripts/backtest_tws_session.py`, `scripts/visualize.py`, `scripts/backtest_multitimeframe.py`

| Hop | Code | What actually happens | Evidence |
|---|---|---|---|
| Engine build | `backtest/engine.py:63-420` | `ReplayEngine` builds PaperConfig + default RiskConfig (93-115) | |
| Fill model | engine.py:81-83 | **defaults slippage=0.0, commission=0.0**; fixed `intent_qty=10`, no sizing | |
| Loop | engine.py:239-323 | per bar: `advance_to` → `_check_exits` (117-172) → strategy `update_bar` (291-294) → `TradeIntent(certificate_ref=self._certificate_ref)` (308-321) → `engine.submit_intent` (323) | |
| **CRASH** | `execution/engine.py:886-895` | `certificate_ref="replay-engine-cert"` is not JSON → `ValueError("Execution certificate verification failed")` on first intent. **Reproduced.** | engine.py:84, 891 |
| (Had it passed) | `BacktestAdapter` | fill from bar via BarConservativeFillModel; `positions()` returns `[]` (backtest_adapter.py:80-85), `holdings()` fixed 100000 (87-96) → reconciliation would be meaningless | execution/backtest_adapter.py:51-96 |
| Look-ahead | engine.py:294+306 | **same-bar close fill**: signal from bar t close filled at bar t close; strategy also receives full OHLC of bar t | fills.py:100 |
| Tests | tests/replay/test_replay_engine.py (6), tests/backtest/test_exit_intents.py (28) | **pass only because tests/conftest.py:80-85 monkeypatches `PaperTradingEngine.submit_intent` to skip the certificate gate** | conftest.py:76-85 |

`backtest_multitimeframe.py` is broken twice: never calls `initialize_new_session` (risk gate
restores `Triggered/Halted` from empty store — core/src/risk.rs:742-752) AND hits the cert
gate (backtest_multitimeframe.py:235). `RuntimeEvaluator.register` records definitions that
are never used to gate proposals (runtime/evaluator.py:75-83).

## 3. Path C — Paper trading session — BROKEN

Entry: `scripts/paper_session.py` (1036 lines)

| Hop | Code | What actually happens | Evidence |
|---|---|---|---|
| Config | paper_session.py:370-373 | `--mode simulation\|paper-preflight\|broker-paper`; RiskConfig+PaperConfig at 540-558 | |
| Adapter | paper_session.py:303-332 | TWS→IBKRPaperAdapter; broker-paper→Alpaca; else SimulatedAdapter. paper-preflight uses SimulatedAdapter (no broker) despite its name | |
| Data | paper_session.py:257-272 | `--data-file`→`data/approved.py` (checksum/manifest/freshness); `--tws`→TWSDataFeed; **default = `_synthetic_prices` random-walk fake data** | |
| **Session init** | **ABSENT** | `engine.start(sync_from_broker=...)` at :710, but NO `initialize_new_session` anywhere → on fresh store the gate restores Triggered/Halted | risk.rs:742-752; engine.py:170; only scripts/init_session.py can arm it and the runbook never calls it |
| Strategy | paper_session.py:655-663 | `StrategyBridge(strategy_id=args.strategy, certificate_ref="dummy_cert_for_paper_session")` (bridge.py:34) | |
| Loop | paper_session.py:759-1001 | RTH gate (881-902) → bridge.on_price → TradeIntent → `engine.submit_intent` (914) | |
| **CRASH** | engine.py:886-895 | `"dummy_cert_for_paper_session"` is not a valid certificate → ValueError; **no try/except in the loop → session process dies on first signal** | bridge.py:34; paper_session.py:914 |
| (Had it passed) | engine.py:948-1231 | cert → adapter health → kill switch → instrument validation → circuit breaker → Rust RiskGate (1029-1037) → risk token (1086-1094, secret hardcoded `'TITAN_RISK_SECRET_KEY'`) → OrderStateMachine persisted → `adapter.place_order` (1122) → `_absorb_broker_fill` (638-739) → PortfolioEngine.apply_fill (core/src/portfolio.rs:103) → `_save_state` (1214) | |
| Fill polling | engine.py:281-288, 1233-1318 | `_poll_loop` / `poll_fills` | |
| Reconciliation | paper_session.py:930-932 | `engine.reconcile()` every 300s → Rust `ReconciliationEngine.compare` (reconciliation.rs:131-250); Critical drift → kill switch | |
| Costs | engine.py:736 | **fees hardcoded `Money("0")`** — paper fills are cost-free | |
| Research feedback | only with `--qualification-db --shadow` | ShadowRunner → ResearchDB (research/shadow.py:152-166). Otherwise metrics JSON only; **no PnL ever flows back to research** | |

Kill-switch release: `release_kill_switch.signal` + `ReleaseAuthorization` dual approval
(paper_session.py:776-810; engine.py:1623-1711) — real and wired.

**Status: The engine machinery (risk, orders, portfolio, reconciliation) is real, wired and
tested — but the admission contract (certificate) makes paper execution structurally
impossible today. No certificate is issued anywhere outside tests** (`create_signed_certificate`
defined at promotion_certificate.py:113,152, called only from tests; `PromotionGate.promote()`
writes DB status only, promotion.py:508-529 — never a certificate).

## 4. Subsystem status ledger

| Subsystem | Status | Evidence |
|---|---|---|
| Market data ingest (file) | IMPLEMENTED (works) | data/ingest.py |
| Market data live (TWS/Alpaca/Polygon) | PARTIALLY (code real; untested live on this machine; TWS history dirs absent) | tws_feed.py; alpaca_feed.py; polygon_feed.py |
| Fincept feed/adapter | SCAFFOLDING — import of `fincept_native` always fails; sibling repo is a vendored C++ terminal, not a dependency | fincept_adapter.py:28; sibling repo audit |
| Features / feature graph | UNWIRED (imported only by tests) | runtime/feature_graph.py |
| Strategies (10 registered) | IMPLEMENTED, all `qualified_variants=frozenset()` | registrations.py:19-164 |
| Research backtest harness | IMPLEMENTED, works end-to-end | scripts/backtest_strategies.py |
| ReplayEngine backtest | BROKEN (cert gate; same-bar fills; zero-cost defaults) | backtest/engine.py |
| Qualification DB | PARTIALLY (schema real; production DB absent) | research/db.py |
| Promotion gate | IMPLEMENTED (fail-closed, real) but artifact gate UNWIRED; and bypassed by Path-1 direct DB writes | promotion.py; qualification_pipeline.py:479-488 |
| Rust risk core | IMPLEMENTED + wired + tested | core/src/risk.rs; engine.py:1029-1037 |
| Rust orders | IMPLEMENTED + wired + tested | core/src/orders.rs |
| Rust portfolio | IMPLEMENTED + wired + tested | core/src/portfolio.rs |
| Rust reconciliation | IMPLEMENTED + wired + tested | core/src/reconciliation.rs |
| Certificate admission | IMPLEMENTED (default deny) — and the binding constraint: nothing can trade | engine.py:886-946 |
| Paper engine order flow | IMPLEMENTED but unreachable in production (cert) | engine.py:948-1231 |
| Stop/TP/trailing at execution | DOCUMENTED ONLY — no exit-order manager in the engine; exists only in backtest replay | ADR-021; engine.py has none |
| TWAP | DISABLED ("execution-integrity freeze", engine.py:1053-1064) | |
| Memory subsystem | DEAD in production (imported by nothing except tests) | mcp_bridge → vector_memory |
| Multitimeframe runtime | DOCUMENTED ONLY — "NOT STARTED" per knowledge/sessions/multitimeframe-paper-2026-07-24.md; not wired into paper_session.py | |
| Monte Carlo | DOCUMENTED ONLY — no code exists | ARCHITECTURE.md:20 |
| Walk-forward | IMPLEMENTED (walkforward.py, harness.py:383-412) | |
| Data freeze (ADR-026) | DOCUMENTED ONLY — no enforcement in code; violated post-freeze (EXP-00031 re-uses exhausted window) | |
| Monitor/supervise scripts | DEAD on Linux (hardcoded Windows paths, `D:\projects\Project TITAN`) | monitor_paper.py:5-15; supervise_paper_session.sh:8 |

## 5. Documented-vs-actual divergences (the sharpest ones)

1. **README.md:36-41 "no bad trade was ever placed… platform remains intact, tested"** — the only complete engine E2E with a real certificate is tests/e2e/test_profit_engine_e2e.py; every production entrypoint crashes at the gate. LIKELY: no paper session has ever completed an accepted order in the current code state (`logs/` holds 1 entry; the only `.titan_state.db` was created by this audit's own test run at 2026-09-29 12:58 — test-generated, not session-generated).
2. **Runbook restart** (docs/runbooks/paper-session.md:63-72) claims "System state: ACTIVE" after warmup — that string exists only in cli.py:128; paper_session.py starts HALTED unless init_session.py ran first.
3. **Runbook MTF metrics** (paper-session.md:31-34) `evaluations.<tf>` etc. — none exist in `_metrics_integration.py:14-54`.
4. **CLI `titan risk release`** (cli.py:56-81) releases the kill switch with single-click confirmation, no dual approval, no reconcile — violating the invariant ARCHITECTURE.md:63-64 that the engine's own release path (paper_session.py:776-810) enforces.
5. **"HMAC-signed order intents"** (README.md:21) — actually SHA-256(key+payload) hex with hardcoded default secret `'TITAN_RISK_SECRET_KEY'` (engine.py:1086; messages.rs:400-421).
6. **docs/phase-j/README.md:80 references `HealthReporter`** — class does not exist (operations/telemetry.py:9-33).
7. **Uncommitted deletions**: scripts/ibkr_paper_session.py, scripts/nautilus_backtest*.py, tests/adapters/test_paper_session_admission.py are staged-deleted, but backtest_multitimeframe.py:1 still documents mirroring the deleted flow.
8. **Python version**: runbook says 3.14+; pyproject.toml:9 requires >=3.12; the shipped .so is cp313.

## 6. Single most complete path that exists today

**Engine path as exercised by tests/e2e/test_profit_engine_e2e.py** — real unpatched
`submit_intent` with a valid Ed25519 certificate (test_profit_engine_e2e.py:212-232, 940,
946-966): data→signal→intent→Rust risk gate→certificate→adapter→fill→Rust portfolio→Rust
reconciliation. It works ONLY inside that test. No production entrypoint can reproduce it
because no production entrypoint obtains a certificate.

For production entrypoints, the most complete working path is the research harness
(Path A) — which contains none of that machinery.

**Primary hypothesis for "no useful trading results"**: paper mode cannot trade at all —
(a) no session initialization in the entrypoint → fail-closed HALTED; (b) once armed via
init_session.py, the first intent crashes the process at the certificate gate; (c) engine
backtests crash identically; (d) the only runnable backtest path never feeds the trading
engine and its documented outcome is 0 surviving strategies.
