# TITAN CURRENT STATE — What Is Actually Here

**Date:** 2026-09-29. Traced from source, not from docs.

## 1. What can TITAN really do today?

| Capability | Real? | Evidence |
|---|---|---|
| Persist an event log (WAL SQLite) | **Yes** | `core/src/event_store.rs:25` |
| Evaluate an 11-rule deterministic risk gate | **Yes** | `core/src/risk.rs:273`; mutation M16 (bypass) and M12 (10× looser) were **killed** |
| Maintain a `rust_decimal` position/PnL ledger | **Yes** | `core/src/portfolio.rs:103,171-221`; PnL sign-flip failed **35 tests** |
| Run an order state machine (20 edges) | **Yes** | `core/src/orders.rs:74` |
| Detect broker/portfolio drift | **Yes** | `core/src/reconciliation.rs:131`, called `engine.py:1372` |
| Sign/verify Ed25519 promotion certificates | **Yes** | `engine.py:890-895` |
| Talk to IBKR / Alpaca | **Yes** | real `ibapi` (`ibkr_adapter.py:13-16`), real `alpaca-py` (`alpaca_adapter.py:9-12`) |
| Fetch OHLCV (daily + intraday) | **Yes** | `tws_feed.py:330`, `alpaca_feed.py:74,115` |
| Fetch macro (FRED/ECB) | **Yes** | `data/macro_rates.py` — but dead code, no prod importer |
| **Place a single order in a paper session** | **NO** | crashes on first signal — see §8 |
| **Backtest a strategy correctly** | **NO** | long-only, 2× PnL, `sqrt(252)` on bars |
| **Reject a strategy that fails its own gates** | **NO** | failed gates stored as strings, never detected |
| **Run walk-forward validation** | **NO** | `harness.py:383-412` does no training |
| **Run Monte Carlo** | **NO** | 0 implementations anywhere |
| **Call an LLM** | **NO** | 172 LOC in `memory/`, zero model calls |
| **Reproduce its own research** | **NO** | core datasets absent from disk |

## 2. What markets can it actually operate on?

**None end-to-end.** Adapters exist for IBKR (multi-asset), Alpaca, and a simulator, but the
only session runner crashes. Research data on disk covers EURUSD/GBPUSD 5m (21 MB), G10 daily
(92 KB), FRED (3.3 MB), gold (1.4 MB), 2 days of intraday. Crypto and equities datasets are
**absent**.

## 3. Which strategies actually run?

10 registered (`registrations.py`), all reachable via `--strategy` in the paper session.
**6 of 10 crash on a daily-close feed** — `vwap-reversion` and `orb` require full OHLC bar
dicts, but `bridge.py:110` passes `{"close": price}` whenever `bar is None`, which is always
the case in `paper_session.py` daily mode:

```
TypeError: 'float' object is not an instance of 'str'
```

## 4. Which strategies have actual historical evidence?

**One.** EXP-00016 (intraday momentum falsified): IC −0.0834, n = 12,384, bootstrap CI
[−0.102, −0.067], consistent across 3 temporal thirds and 2 pairs. This is a sound negative
result and should be kept.

Everything else is either void (the n=1 screen), mis-instrumented (10–20 bps FX cost,
long-only harness, `sqrt(252)`), or unreproducible (absent datasets).

## 5. Which have paper-trading evidence?

**None.** No paper session has ever completed a trade. There is no live/paper PnL in the
research DB — zero `ResearchDB` references in `execution/` or `strategies/`. The only
research feedback path is `ShadowRunner` → SQLite (`shadow.py:152-166`).

## 6. Which parts exist only as architecture?

- 5 JSON schemas in `contracts/` — "imported by all producers/consumers" per
  `PROJECT_STRUCTURE.md:44`; **zero Python imports**.
- `correlation_id` end-to-end tracing — never populated; `_trace_decision` no-ops (`engine.py:585`).
- `RiskDecisionRecorded` — fields exist in `messages.rs:267`, never written.
- `RiskDecision` persistence — `Risk.spec.md:44` says "All decisions are persisted";
  the dataclass is constructed **nowhere**.
- 15 of 25 Prometheus metrics — never written by any code path.

## 7. Which parts are dead or disconnected?

**Imported by nothing outside tests (0 prod importers):**
`research/validator.py` (407 LOC) · `research/library.py` · `research/dataset.py` ·
`registrations.py` · `crypto_screen_00{2,3,4}.py` · `equities_factor_screen_006.py` ·
`equities_event_screen_00{7,8}.py` (~3,300 LOC, test-only) · `data/macro_rates.py` ·
`data/calendar_forex.py` · `strategies/hrp_allocator.py` · `strategies/rebalancing.py` ·
`strategies/pipeline.py` · `runtime/feature_graph.py` · `execution/fincept_adapter.py` ·
`memory/distillation.py`

**Dead Rust exports:** `TrailingConfig`, `PositionSide`, `PortfolioSnapshot`, `PositionDrift`.

**Dead entrypoints:** `backtest_multitimeframe.py` (TypeError) · `cli.py:127` (TypeError) ·
`paper_session.py:728 --dashboard` (module gitignored, absent) ·
`supervise_paper_session.sh` / `run_tws_paper_loop.sh` (hardcoded **Windows** path
`/d/projects/Project TITAN` on a Linux checkout).

## 8. What is the real execution capability?

**Zero.** Traced end to end:

```
paper_session.py:906   intent = bridge.on_price(...)
paper_session.py:914   result = engine.submit_intent(intent)   # no try/except
  engine.py:891          cert_data = json.loads(cert_json)     # "dummy_cert_for_paper_session"
  engine.py:895          raise ValueError("...verification failed")
=> uncaught ValueError kills the session process
```

`bridge.py:34` defaults `certificate_ref = "dummy_cert_for_paper_session"`; `engine.py:890`
`json.loads()` it. The 1180-test suite is green because `tests/conftest.py:81-85` is an
**autouse** fixture that replaces `submit_intent` with `_submit_intent_core` — skipping the
certificate gate — for every test except those with `e2e`/`adversarial`/`test_execution_integrity`
in the node id.

Even with the cert fixed: a fresh engine is fail-closed by design
(`trading_state=Halted kill_switch=Triggered` before `start()`), and the runner skips signal
generation outside 09:35–16:00 ET. `init_session.py` is required first.

## 9. What is the real research capability?

**Instruments exist; the instrument is broken.** The screens, the preregistration format, the
evidence bundles, the cost-aware backtest, and the negative-results discipline are all real
and well-designed *as artifacts*. Executed against reality they produce void measurements:
one trade per hypothesis, a 20-pip FX cost, a discarded Bonferroni, a fake walk-forward, and
a `replicated` flag hard-wired to make "no survivors" a constant.

## 10. What is the real AI capability?

**None.** 172 LOC in `src/titan/memory/` = **0.6%** of source. Imported only by
`research/mcp_bridge.py` and tests. `embedding_vector` is populated **nowhere**;
`search_similar_trades` can never match. `mcp_bridge.py:66` returns **fabricated** strategy
names (`"ma_crossover"`, `"bollinger_breakout"` — neither exists in the registry). Zero LLM
or API calls exist in the codebase.

ADR-0007's "no LLM call on the capital path" is technically true, but only because there is
no LLM call on **any** path.

---

## The five separations

| | Verdict |
|---|---|
| **ARCHITECTURE** | Genuinely good in the Rust core; bloated and partly fictional in the Python/governance layer |
| **IMPLEMENTATION** | Rust: real. Python research: real code, wrong semantics. Python runtime: crashes |
| **VERIFICATION** | 1180 tests pass; mutation testing shows the **metric and strategy-signal layers have ~0% effective coverage** |
| **OPERATION** | Never operated. Zero orders placed. Zero paper evidence |
| **ECONOMIC USEFULNESS** | **Zero, and currently unmeasurable** |
