# ARCHITECTURE HEALTH REPORT

**Date:** 2026-09-29.

## 1. The Rust/Python boundary — sound, and inverted from the docs

`core/src/lib.rs:20` — a clean PyO3 seam, 33 registered types, no leakage. ~2,882 non-test
Rust LOC. Every core economic type crosses it:

| Rust module | Called from | Notes |
|---|---|---|
| `risk.rs:273` `RiskGate.evaluate` | `engine.py:1029` | 11-rule deterministic chain |
| `portfolio.rs:103` `apply_fill` | fill path | `rust_decimal` — correct for money |
| `orders.rs:74` `OrderStateMachine` | execution | 20-edge transition table |
| `event_store.rs:25` `EventStore` | persistence | WAL SQLite + 4 indexes |
| `reconciliation.rs:131` `compare` | `engine.py:1372` | 5%/1% drift fractions |

**`REPOSITORY_CATALOG.md:9` says the Rust core is "exists but not wired". This is inverted.**
The Rust core **is** wired (`engine.py:1029` risk, `:1372` recon, portfolio on every fill).
The Python session runner is what isn't.

**Is Rust earning its keep?** Yes. `Decimal` + `rusqlite` + a state machine is exactly the
right combination for money and durability, floats never touch economic values, and mutation
testing could not break it. **The Rust-vs-Python debate is a distraction** — every defect found
in this audit is in the Python research and runtime layers, not the kernel.

## 2. The single biggest structural problem: duplicate systems

**6+ independent backtest simulators:**

| Simulator | Location |
|---|---|
| `ReplayEngine` | `backtest/engine.py:63` |
| `simulate_crypto` | `backtest/crypto_simulator.py:91` |
| `simulate_factor_portfolio` | `backtest/factor_simulator.py:181` |
| `simulate_crypto_maker_carry` **and** `simulate_crypto_taker_carry` | `research/crypto_screen_004.py:159, :395` |
| `simulate_equities_micro` | `research/equities_micro_screen_001.py:170` |
| equity/event simulators | `research/equities_event_screen_007.py:169`, `_008.py:194`, `equities_factor_screen_006.py:97` |
| FX `backtest()` | `research/traderdev_fx_screen.py:302` |

**`_compute_max_drawdown` is copy-pasted 5×** — `factor_simulator.py:174`,
`equities_factor_screen_006.py:90`, `equities_event_screen_007.py:93`,
`equities_event_screen_008.py:93`, `render/report.py:6`. **This is the direct mechanism by
which mutation M11 (inverted drawdown sign) survived:** five chances to disagree, and only one
was exercised.

**6 independent cost models:** `crypto_costs.py:11`, `factor_simulator.py:24`, `fx_costs.py:13`,
`fills.py:24`, plus inline logic in `promotion.py`, `harness.py`, `walkforward.py`, `shadow.py`,
and 5 `research/*.py`. **This is the direct mechanism of the 0.9 bp vs 20 bp contradiction**
that killed EXP-00022.

**Consequence:** cross-checking is impossible. The EXP-00031 "independent reproduction" *was*
the cross-check — and it produced 54 trades where the original produced 163, because it used a
different position model, a different trailing parameter (3.0×range vs 2.0×ATR-14), and a
different fee schedule. Nobody noticed, because nobody compared trade counts.

## 3. God object

`src/titan/execution/engine.py` — **1,752 lines**, 29 imports spanning all 16 Rust core types
plus `operations.logging`, `data.feed_health`, `risk.*`, and `research.promotion_certificate`.
Longest line: 168 chars at `:1159`. **There is no broker/strategy/risk boundary in this file —
it *is* the boundary.** Cert verification, scope binding, risk, circuit breaking, execution,
fill absorption, reconciliation, and authorization all live in one class.

## 4. Layering violation

`src/titan/execution/engine.py:48`:
```python
from titan.research.promotion_certificate import PromotionCertificateRegistry, Certificate
```
**The execution hot path depends on the research layer.** `backtest/` and `risk/` are clean.
No import-linter exists to prevent it.

## 5. State ownership

| State | Owner | Verdict |
|---|---|---|
| Position/PnL/cash | Rust `portfolio.rs` + event store | **Good** — single writer, `Decimal`, WAL |
| Order lifecycle | Rust `orders.rs` | **Good** — explicit 20-edge table |
| Risk verdict | Rust `risk.rs` | Good compute, but **never persisted** (`RiskDecision` constructed nowhere) |
| `_last_prices` | Python `paper_session.py:861` written directly | **Bad** — bypasses the engine, so `risk.rs:706` correlation rule can never fire |
| Bridge position/side | `bridge.py` JSON sidecar | Acceptable, admission-gated |
| Research runs | `titan_research.db` SQLite | Fine, but `knowledge/experiments/` empty |

The pattern is good in Rust and leaky in Python, because the Python layer writes engine
internals directly rather than calling methods.

## 6. Event architecture

- `EventStore` with WAL + 4 indexes: **real and sound.**
- `EventEnvelope::new` **auto-generates** `correlation_id` (`messages.rs:60`) — so it is never
  *propagated*. `paper_session.py:914` passes the default `""`; `_trace_decision` no-ops on empty
  (`engine.py:585`). **The entire decision-trace subsystem is inert in the runtime.**
- Envelopes written with `schema_version=100` (`messages.rs:58`) while `contracts/*.schema.json`
  declare `v1` and are **never imported by any Python code**.

## 7. Configuration

`risk/limits.py` — `DEFAULT_CFG` merged with overrides into `RiskConfig`. **Genuinely wired to
behaviour** (mutation M12, 10× looser limits, was killed). This is the one config path that
works properly. `engine.py:1086` is the counter-example: the HMAC secret is the literal
`"TITAN_RISK_SECRET_KEY"`.

## 8. AI boundary

`src/titan/memory/` = **172 LOC = 0.6%** of source. Imported only by `research/mcp_bridge.py`
and tests. **Zero LLM/API calls exist in the codebase.** `embedding_vector` is populated
nowhere; `search_similar_trades` can never match; `mcp_bridge.py:66` returns fabricated strategy
names. ADR-0007's "no LLM on the capital path" holds because there is no LLM on **any** path.
**The AI boundary is clean, because the AI subsystem is dead.**

## 9. Complexity verdict

### Overengineered
- 1,752-line `engine.py` god object
- 6+ backtest simulators, 6 cost models, 5 copies of max-drawdown
- 34 ADRs, ~14.5k doc LOC, ~140 governance files vs ~27.4k code LOC
- `AI_GOVERNANCE.md` specifying embedding models and access classes for a system with 172 LOC
  and no model
- 4 specifications describing pipeline stages (`liquidity/impact`, `broker/session health`)
  that are absent from `risk.rs:283-319`

### Underengineered
- **No statistical layer at all** — no DSR, no PSR, no PBO, no CPCV, no purge/embargo, no Monte
  Carlo (required by `docs/reference/RESEARCH_PROTOCOL.md:47`; **0 implementations**)
- **No trial ledger** — N is never recorded as data, so multiple-testing exposure is invisible
- **No absolute-value economic assertions** — one test in 1180
- **No per-instrument cost source of truth**
- **No coverage floor, no mutation testing, no import-linter**
- Portfolio construction (HRP, rebalancing, covariance) is **all dead code**

### Architecture that makes research slower
Six simulators means every research question must be re-validated per implementation. The
2,000-line parameter surface (`ema9vwap_parameter_surface.py`) reports **no significance
statistic** because there is no statistics module to compute one. **The absence of a statistics
layer is the architectural root cause of the entire overfitting exposure.**

### Architecture that makes experimentation harder
Adding a market means writing a new simulator *and* a new cost model *and* a new screen
*and* new gates. Five of the six post-pivot "programs" wrote their own simulator. That is the
6-simulator problem's cause, not its consequence.

## 10. What to do

**Do not** restructure the engine into microservices. `PROJECT_TITAN.md:40` gets this right:
*"process boundaries are introduced only when isolation, latency, scale, or ownership evidence
justifies them."* There is no such evidence.

**Do:**
1. **One backtest core, one cost model, one metrics module.** Delete 5 of 6 simulators and 4 of
   5 drawdown copies. Every one of the metric defects (C8, C9, C11, C12) exists *because* there
   are five implementations.
2. **Vendor a statistics module** (`Vibe-Trading/quantlib` — DSR, PSR, PBO, purged/CPCV). This
   is the single largest structural gap and it is an import, not a build.
3. **Split `engine.py`** on the boundaries it already has: cert/scope, risk, execution, recon.
   Mechanical extraction, no behaviour change, no new abstractions.
4. **Add an import-linter** to keep `execution/` out of `research/`.
5. **Propagate `correlation_id`** or delete the decision-trace subsystem. Do not keep an inert
   tracing facility — it is worse than none, because it is documented as a success criterion
   (`PROJECT_TITAN.md:52`).
