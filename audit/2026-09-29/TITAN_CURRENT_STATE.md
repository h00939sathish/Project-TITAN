# TITAN CURRENT STATE — 2026-09-29

Answers to the ten questions, with the five-layer separation required
(ARCHITECTURE / IMPLEMENTATION / VERIFICATION / OPERATION / ECONOMIC USEFULNESS).

---

## 1. What can TITAN really do today?

- **Run honest strategy research on OHLCV data**: ingest → validate → backtest (next-bar
  fills, cost models) → record results in evidence bundles. This works end-to-end and has
  been used ~40 times. (scripts/backtest_strategies.py; research/ evidence bundles)
- **Enforce a fail-closed risk/order/portfolio/reconciliation core in Rust**, exercised by
  a green 1180-test suite and one true E2E test with a real certificate
  (tests/e2e/test_profit_engine_e2e.py).
- **Paper-trade: NO.** The certificate admission gate has no production issuance path, so
  every real entrypoint (paper_session.py, ReplayEngine, papertrade.py) crashes or halts
  before the first order.
- **Promote a strategy to paper: NO.** Zero QUALIFIED rows; the promotion DB does not exist
  in the repo; `PromotionGate.promote()` never issues a certificate.

## 2. What markets can it actually operate on?

ARCHITECTURE: multi-asset (equities, FX, crypto, gold) with adapters for IBKR TWS, Alpaca,
Polygon, Fincept.
REALITY (data on disk): 1 year of 5m/daily FX **midpoint** data for EURUSD/GBPUSD (+1 month
AUDUSD); 26y daily gold/DBC; FRED macro series (6 files corrupt); ~2-week intraday slices
of EURUSD/SPY. No 1m bid/ask, no multi-year 1h/4h, no equity intraday history, no raw
crypto data. OPERATION: none of it can reach an order anyway (cert gate).

## 3. Which strategies actually run?

Ten are registered (registrations.py:19-164): ma-crossover, dual-ma, mean-reversion,
time-series-momentum, rsi, bollinger, volatility-regime, orb, vwap-reversion,
traderdev-ema9-vwap. All ship `qualified_variants=frozenset()`.
- In the research harness: all ten have been backtested repeatedly (e.g. SPY daily,
  EURUSD 5m/15m/1h/4h).
- In paper mode: only the default `ma-crossover` (paper_session.py:343) would run — on
  synthetic random-walk data by default — and it crashes at the certificate gate.
- ORB produces 0 trades in every per-timeframe backtest (backtest_per_timeframe_results.json).

## 4. Which strategies have actual historical evidence?

All ten have backtest records (research/backtest_results_summary.json,
backtest_per_timeframe_results.json, ~30 experiment bundles). Headline, cost-aware:
- Best classic result: SPY daily ma-crossover 2020-24 +2.27%, Sharpe 0.91, PF 2.47, 68
  trades — vs buy-and-hold 81.06% over the same window (i.e. the strategy added negative
  value vs passive).
- Only FX candidate with positive net pips over 12 months: traderdev-ema9-vwap 4h
  (EURUSD +71.8 pips, GBPUSD +336.5 pips, Dukascopy, real spread + 0.5bps slip + 0.2bps
  comm) — and it FAILS the promotion gate 4/7 (ema9vwap_gate_diagnostic.json).
- Everything else: net ≈ 0 or negative after costs.

## 5. Which strategies have paper-trading evidence?

**None.** The only execution ever certified was a 1-share SPY BUY/SELL on Alpaca paper on
2026-07-14 — an adapter certification, not strategy evidence
(knowledge/certifications/one-order-paper-execution-2026-07-14.md). No strategy has ever
produced a paper-trading record that could feed the promotion gate's shadow-trade gates
(≥5 shadow trades, win rate ≥0.3) — which is precisely why the one gate evaluation on
record failed shadow_sufficiency.

## 6. Which parts only exist as architecture?

- Multitimeframe runtime (ADR-017): "NOT STARTED" per its own session note; not wired into
  paper_session.py; its metrics don't exist in the metrics registry.
- Monte Carlo (ARCHITECTURE.md:20): no code anywhere.
- Stop/TP/trailing orders at execution (ADR-021): no exit-order manager in the engine;
  exists only in the backtest replay engine.
- Features / feature graph layer: imported only by tests.
- Memory subsystem (ADR-007 vector memory): imported by nothing in production.
- Data freeze (ADR-026): policy text only; violated post-freeze.

## 7. Which parts are dead or disconnected?

- src/titan/cli.py — no console script in pyproject.toml, no importer.
- src/titan/research/{classes,cli,dataset,library,registrations,validator}.py — no importers.
- fincept_adapter/fincept_feed — import-safe but the `fincept_native` module cannot exist
  outside the Fincept binary; the sibling repo cannot supply it. Dead live path.
- monitor_paper.py, supervise_paper_session.sh, run_tws_paper_loop.sh,
  paper_session_observer.py — hardcoded Windows paths; dead on this Linux host.
- Promotion artifact gate (`evaluate_from_artifact`, ADR-031) — real code, zero callers.
- BacktestAdapter.positions()/holdings() — stubs returning [] / fixed 100000.

## 8. What is the real execution capability?

A well-built, fail-closed engine that **cannot execute**:
- Order state machine, partial fills, rejects, timeouts, Unknown-resolution: implemented
  in Rust and wired (core/src/orders.rs; engine.py:948-1231).
- Broker adapters: IBKR paper-port-locked (7497/8874), Alpaca, SimulatedAdapter
  (PARTIAL_THEN_FULL/REJECT/TIMEOUT/NEVER_FILL modes), Fincept (dead).
- Admission: certificate gate with Ed25519, scope-bound, nonce single-use — **and no
  certificate is issued anywhere outside tests**. Default deny with no path to yes.
- Costs at execution: **none modeled** — fees hardcoded 0 (engine.py:736), SimulatedAdapter
  fills at limit price with zero costs.

## 9. What is the real research capability?

The strongest part of the project, and the only part that demonstrably works:
- ~40 experiments across FX, crypto, equities, gold with pre-registration, evidence
  bundles, absorbing negative-result sealing, an honest journal, and a fail-closed
  promotion gate that "failed safely, 40 times"
  (research/ALPHA_SEARCH_TERMINAL_REPORT.md:65-67).
- Real cost-aware analyses (e.g. EXP-00019 real-spread follow-up: EURUSD short-rally
  +0.58 pips/day net, +1.95 pips in the 12-16 UTC window; crypto fee-tier analyses
  quantifying maker-fee vs harvestable half-spread).
- Weaknesses: OOS leakage into the plateau-stability gate
  (qualification_pipeline.py:209-225; plateau_detector.py:41-43), a parallel qualification
  path that writes QUALIFIED directly to the DB on weak thresholds
  (qualification_pipeline.py:113-119, 479-488), same-bar fills in ReplayEngine, and a data
  freeze that exists only on paper.

## 10. What is the real AI capability?

An advisory policy (ADR-007) and a memory subsystem that nothing imports. The LLM/memory
layer is architecture, not capability. Given the 2026 external evidence (no publicly
verified LLM trading profitability; most LLM agents lose money in the AI-Trader live
benchmark; the field's own audits find 0/19 reproducible studies), this is not currently a
loss — it is the correct amount of AI to have.

---

## Five-layer verdict

| Layer | Verdict |
|---|---|
| ARCHITECTURE | Strong: single Rust authority for risk/orders/portfolio/reconciliation, deterministic event store, fail-closed defaults, ADR discipline. Comparable in intent to NautilusTrader's Rust core — but smaller and uncompleted. |
| IMPLEMENTATION | Mixed: Rust core real and wired; research harness works; but the promotion→certificate→paper chain is unimplemented at its most critical link, and four divergent fill/cost models coexist. |
| VERIFICATION | Misleading: 1180 tests pass while every production entrypoint crashes — because conftest.py:76-85 monkeypatches the gate out. Only one test exercises the real path. |
| OPERATION | Non-existent: no session has completed an order in the current code state; ops scripts target a Windows machine; the qualification DB does not exist. |
| ECONOMIC USEFULNESS | Today: negative-to-zero as a trading system. As a research record: genuinely useful — a rare, honest, ~40-experiment negative-result corpus with cost-aware economics. |

## What TITAN is, in one paragraph

TITAN is a research-governance platform with a small but real Rust execution core, whose
research loop works and whose trading loop is broken at the exact seam that matters
(promotion → execution certificate), and which has honestly proven that the strategy
classes it searched (simple directional/regime/macro OHLCV signals) contain no harvestable
edge at retail cost levels on the data it had. The durable asset is the platform and the
negative record, not the (non-existent) alpha — which is also what the project itself
concluded (ALPHA_SEARCH_TERMINAL_REPORT.md:97).
