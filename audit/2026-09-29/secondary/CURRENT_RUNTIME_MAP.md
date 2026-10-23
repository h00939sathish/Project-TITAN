# CURRENT RUNTIME MAP — Traced, Not Documented

**Date:** 2026-09-29. Every row verified against source.

## The only end-to-end entrypoint

`scripts/paper_session.py:360 main()`. There is **no console script** in `pyproject.toml`
(0 `[project.scripts]`). `src/titan/cli.py` is reachable only as `python -m titan.cli`, and
`cli.py:127` raises `TypeError`.

## Pipeline, transition by transition

| # | Transition | Actual function | In → Out | Validation | Persistence | Tests |
|---|---|---|---|---|---|---|
| 1 | **Market data** | `StrategyRunner.tick` `paper_session.py:211`; synthetic fallback `_synthetic_prices:257`; approved CSV `load_approved` `data/approved.py:40` | `list[float]` → prices+idx | checksum, min bars, staleness `approved.py:78-88` | none | `tests/integration/test_data_pipeline.py` |
| 2 | **Normalization** | `normalize_row` `data/normalize.py:35`; `validate_and_quarantine` `data/quality.py:37` | CSV dict → dict/quarantine | OHLCV shape, business-day gap | none | `tests/data/` |
| 3 | **Features** | **NONE.** The signal fn *is* the feature computation: `make_strategy_signal_fn` `research/harness.py:174-225` wraps `bar["close"]` into `MovingAverageCrossover.update` `strategies/moving_average.py:24` | `{"close": float}` → `"BUY"/"SELL"/None` | none | none | `test_moving_average.py` |
| 4 | **Strategy → Intent** | `StrategyBridge.on_price` `strategies/bridge.py:85-188` | price, bar_date, bar → `TradeIntent:161` | bar-date dedup `:103`, position/side check `:128-136`, regime suppression `:123` | `.bridge_state` JSON `paper_session.py:1009` | `test_bridge.py` |
| 5 | **Intent admission** | `PaperTradingEngine.submit_intent` `execution/engine.py:882` | `TradeIntent` → `OrderResult` or **raises** | shadow `:883`, Ed25519 cert `:890-895`, 6 scope bindings `:901-940`, nonce replay `:941` | none | **only via conftest patch** |
| 6 | **Circuit breaker** | `CircuitBreaker.record_intent` `risk/circuit_breaker.py:54` @ `engine.py:996` | — → `(bool, reason)` | 10/s, 100/min, 3 errors | in-memory only | `test_circuit_breaker_wired.py` |
| 7 | **Risk gate** | `RiskGate.evaluate` (Rust) `core/src/risk.rs:273` @ `engine.py:1029` | intent, pos, exposure, DD, daily loss, side, correlations → `RiskVerdict` | 11 rules, short-circuit; kill switch, trading state, freshness, eligibility, notional, qty, position, exposure, DD, daily loss, side consistency, correlation | **never persisted** | `test_gate.py` (10 rules each) |
| 8 | **Approved order** | `ApprovedOrderIntent` `engine.py:1070`; risk token `:1086-1094` | verdict → signed intent | HMAC verify (default secret is the literal string `"TITAN_RISK_SECRET_KEY"`) | none | `test_risk_token.py` |
| 9 | **Execution** | `adapter.place_order` `engine.py:1122` | `ApprovedOrderIntent` → `BrokerOrderAcknowledgement` | adapter-specific | `OrderSubmitted`/`OrderAcknowledged` `:1108,1176` | `tests/adapters/` |
| 10 | **Broker** | `SimulatedAdapter` `execution/simulated_adapter.py:49`; `IBKRPaperAdapter` `ibkr_adapter.py:124`; `AlpacaAdapter` `alpaca_adapter.py:52`; `FinceptAdapter` **STUB** `fincept_adapter.py:29` | — → ack | auth, heartbeat, https-only base URL | none | `test_multi_asset_adapter.py` |
| 11 | **Fill** | `_absorb_broker_fill` `engine.py:638-739` (single delta path) | cumulative qty → `BrokerFill` | `delta <= 0` no-op `:658` | `PositionOpened/Changed/Closed`, `OrderFilled` `:688-708` | `test_duplicate_fill.py` |
| 12 | **Portfolio** | `PortfolioEngine.apply_fill` (Rust) `core/src/portfolio.rs:103` | fill → cash, pos, realized PnL | cost-basis realized/unrealized | event store | `test_spot_metal_simulation.py` |
| 13 | **Reconciliation** | `ReconciliationEngine.compare` (Rust) `core/src/reconciliation.rs:131` @ `engine.py:1372` | portfolio + broker truth → drift severity | 5% / 1% fractions | none | `test_restart.py` |
| 14 | **Research feedback** | `ShadowRunner._write_events` `research/shadow.py:152` → `ResearchDB.log_shadow_event` | shadow events → SQLite rows | none | research DB | `test_shadow_events_path.py` |

## Where the path breaks

**Primary break — the session dies on the first signal:**

```
paper_session.py:906   intent = bridge.on_price(...)   # cert = "dummy_cert_for_paper_session" (bridge.py:34)
paper_session.py:914   result = engine.submit_intent(intent)   # ← no try/except
  engine.py:891          cert_data = json.loads(cert_json)
  engine.py:895          raise ValueError("...verification failed")
```

Same failure in `scripts/backtest_smoke.py:152` and `scripts/papertrade.py:144,166`.

**Why 1180 tests are green:** `tests/conftest.py:81-85` is an `autouse` fixture replacing
`submit_intent` with `_submit_intent_core` for every test whose node id lacks
`e2e` / `adversarial` / `test_execution_integrity`.

**Secondary breaks even after the cert is fixed:**
1. `paper_session.py:893-895` skips signals outside 09:35–16:00 ET and on weekends — at audit
   time (07:12 UTC = 03:12 ET) every bar `continue`s.
2. A fresh engine is fail-closed (`probe4.py`: `trading_state=Halted kill_switch=Triggered`
   before *and* after `start()`). `init_session.py` must run first.
3. `paper_session.py:861` writes `_last_prices` directly instead of calling
   `engine.update_price()`, so the correlation risk rule (`risk.rs:706`) can never fire.
4. `_require_release_authorization` `engine.py:1607` does not pass `authorized_approvers`
   (unlike init at `:1524-1526`) — any 2 distinct strings pass dual authorization.

## Architecture vs reality — the divergent claims

| Claim | Reality | Evidence |
|---|---|---|
| `Risk.spec.md:44` "All decisions are persisted" | **False.** `RiskDecision(...)` constructed nowhere in `src/` or `scripts/` | grep: 0 prod sites |
| `ARCHITECTURE.md` "`correlation_id` follows a decision end to end" | **False.** `EventEnvelope::new` fabricates one (`messages.rs:60`); runner passes default `""`; `_trace_decision` no-ops on empty | `engine.py:585` |
| `SYSTEM_CONTRACTS.md` `RiskDecisionRecorded` "includes every evaluated rule/version, inputs digest, limit snapshot" | Fields exist (`messages.rs:267`), never populated | — |
| `PROJECT_STRUCTURE.md:44` contracts "imported by all producers/consumers" | **Zero** Python imports. Events written with `schema_version=100` vs schema `v1` | `messages.rs:58` |
| `specifications/StrategyRuntime.spec.md` "Implemented in `multitimeframe_runtime.py`, `runtime/evaluator.py`" | Not imported by `paper_session.py`; the one script that does use them crashes with `TypeError` | `backtest_multitimeframe.py:175` |
| `Risk.spec.md` pipeline includes "liquidity/impact" and "broker/session health" | **Absent** from `core/src/risk.rs:283-319` (8 checks, not the documented set) | — |
| `AI_GOVERNANCE.md:17` vector memory stores "embedding model/version" | `TradeMemoryRecord` (`memory/vector_memory.py:84-97`) has none; no embedding model exists | — |
| `REPOSITORY_CATALOG.md:9` Rust core "exists but not wired" | **Inverted.** The Rust core *is* wired (`engine.py:1029` risk, `:1372` recon, `portfolio.rs`); the Python session runner is what isn't | — |
| `paper_session.py:34` assumes a monitor exists | `scripts/monitor.py` has no argparse, no `--help` | — |
| `scripts/ops` assumes a dashboard | `dashboard/` is gitignored (`.gitignore:40`) and absent → `ModuleNotFoundError` | — |

## LOC distribution

| Category | LOC | % | Note |
|---|---|---|---|
| Research | 17,904 | 62.7% | `src/titan/research` 10,600 + `backtest` 1,477 + `research/` 3,832 |
| Trading logic | 7,228 | 25.3% | execution 3,713 + strategies 2,442 + risk 455 + runtime 320 |
| Data | 2,572 | 9.0% | |
| Infrastructure | 687 | 2.4% | |
| **AI** | **172** | **0.6%** | `src/titan/memory` |
| Rust core | 4,132 | — | 2,882 non-test |
| tests | 23,082 | — | 1,180 pass / 17 skip |
| docs (md) | ~14,572 | — | ~140 files, 34 ADRs |
