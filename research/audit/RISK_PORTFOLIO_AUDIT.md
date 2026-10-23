# RISK & PORTFOLIO AUDIT

**Date:** 2026-09-29.

## Headline

**The risk system is the best-engineered part of TITAN and is not the bottleneck. It is also
not preventing anything, because nothing ever reaches it.**

The brief asks specifically: *is TITAN's risk system unintentionally preventing valid strategies
from expressing their edge?* **No — provably not.** Zero orders have ever been placed, so the
risk gate has vetoed nothing. And mutation testing shows it is genuinely wired to behaviour:
bypassing the gate (M16) and loosening limits 10× (M12) were both **killed** by the suite.

## 1. Risk engine audit

`core/src/risk.rs:273 RiskGate.evaluate` — 11 rules, short-circuiting, called at
`engine.py:1029`:

| # | Check | Verdict |
|---|---|---|
| 1 | `check_kill_switch` | **Fail-closed by default** — `load_or_default` `risk.rs:450` returns Triggered/Halted on an empty store. **Verified empirically.** Correct. |
| 2 | `check_trading_state` | Correct. Requires explicit `init_session.py`. |
| 3 | `check_data_freshness` | Correct. |
| 4 | `check_instrument_eligibility` | Correct. |
| 5 | `check_order_limits` | Correct. **Mutation M12 (10× looser) KILLED** — genuinely wired. |
| 6 | `check_position_limits` (notional, qty, position, exposure, DD, daily loss) | Correct. **Mutation M16 (gate bypass) KILLED.** |
| 7 | `check_side_consistency` | Correct. |
| 8 | `check_correlation` | **CAN NEVER FIRE** — see §3. |
| — | liquidity / impact | **ABSENT** despite `Risk.spec.md` documenting it |
| — | broker / session health | **ABSENT** despite `Risk.spec.md` documenting it |

`risk/limits.py` — `DEFAULT_CFG` merged with overrides into `RiskConfig`. Genuinely wired.
`risk/circuit_breaker.py:54` — `record_intent` at `engine.py:996`, `record_error` at `:1131`,
`record_success` at `:1171`. **All three wired.** 10/s, 100/min, 3 errors.

**Assessment: too weak / appropriate / too restrictive / wired wrong?**
→ **Appropriate in design, completely untested in operation.** It has never been exercised by a
real order. Zero operational evidence.

## 2. Are risk controls blocking valid strategies?

**No. Zero evidence either way, because zero orders exist.** But there is one *real* structural
finding:

**`harness.py` (the research backtest) has NO risk layer at all.** The research path goes
signal → fill → PnL with `Sizer.size` (notional allocation) as the only constraint. The 11-rule
gate, drawdown caps, exposure caps, and daily-loss limits are applied **only in the live/paper
engine**, never in backtests.

**Consequence:** a strategy that the risk gate would reject live can backtest green indefinitely.
The research loop cannot see the risk system's effect on strategy economics at all. This is the
mechanism by which "risk controls suppressing edge" would go **undetected** — the audit question
cannot be answered because the two systems were never connected.

**Recommended:** backtests must report **constrained** performance alongside unconstrained, using
the same gate. A strategy whose Sharpe falls from 0.8 to 0.2 under the real risk layer is a
different investment than one that survives it — and TITAN cannot currently tell them apart.

## 3. Confirmed risk-path defects

| # | Defect | Evidence | Severity |
|---|---|---|---|
| R1 | **Correlation rule can never fire** — `paper_session.py:861` writes `_last_prices` directly instead of calling `engine.update_price()`; `risk.rs:706` reads the engine's own state | verified | **HIGH** — a documented control is inert |
| R2 | **`RiskDecision(...)` constructed nowhere**; `Risk.spec.md:44` "All decisions are persisted" is false | grep 0 prod sites | **HIGH** — rejections live in a log line (`engine.py:1046`) and an in-memory counter |
| R3 | **No live/paper PnL flows back to research** — zero `ResearchDB` references in `execution/` or `strategies/` | grep | HIGH — the feedback loop is one-directional (shadow only) |
| R4 | **Hardcoded HMAC secret** `"TITAN_RISK_SECRET_KEY"` at `engine.py:1086` | verified | **MEDIUM** |
| R5 | **Dual auth weaker on release than on init** — `engine.py:1607` omits `authorized_approvers` (cf. `:1524-1526`); any 2 distinct strings pass | verified | **MEDIUM** |
| R6 | **15 of 25 Prometheus metrics never written**; `cli.py:142` reads `drift_count_critical` → health check always reports "Broker truth matches: YES" | `operations/export.py:79` | **HIGH** — actively false assurance |
| R7 | **Risk layer absent from backtests** (see §2) | `harness.py` | **HIGH** |
| R8 | Dual-authorization is the *only* release control, and the release CLI is broken (`cli.py:127` `TypeError`) | verified | MEDIUM |

## 4. Portfolio construction

| Component | Status | Evidence |
|---|---|---|
| Position/PnL/cash ledger | **Real, good** | `core/src/portfolio.rs:103,171-221,267,311`; `rust_decimal`; PnL sign-flip fails **35 tests** |
| Drawdown tracking | Real | `portfolio.rs:311` |
| Multi-asset accounting | Real | `test_multi_asset_adapter.py`, `test_spot_metal_simulation.py` |
| **Exposure limits** | Real, in the gate | `risk.rs` position limits |
| **Correlation limits** | Real, but **inert** (R1) | `risk.rs:706` |
| **Portfolio construction** | **DEAD CODE** | `strategies/hrp_allocator.py` — zero prod importers |
| **Rebalancing** | **DEAD CODE** | `strategies/rebalancing.py` — zero prod importers |
| **Covariance estimation** | **DEAD CODE** | `strategies/pipeline.py` — zero prod importers |
| **Capital allocation across strategies** | **ABSENT** | No multi-strategy allocator exists |
| **Diversification** | **NOT IMPLEMENTED** | Every experiment is a single instrument or a single factor |
| **Rebalance-grid phase** | **Bug** — IS and OOS rebalance on **different phases** of the monthly cycle | `equities_factor_screen_006.py:136,143` — causal (weights shifted +1 day at `:235`, correctly) but an unforced source of IS/OOS mismatch |

**Portfolio is the most underbuilt layer relative to its importance** — but it is **not the
current bottleneck**, because no strategy has survived to need a portfolio.

## 5. Position sizing

`strategies/sizing.py` `Sizer.size` — notional allocation, step size, minimum quantity,
currency conversion. **Mutation M1 (step-size floor) and M2 (10× position size) both KILLED** —
genuinely tested. The `harness.py` PnL double-count (C6) inflates reported trade values ~2×,
which in turn **inflates `capacity_proxy`** (`results.py:69-73`, avg trade value / avg equity)
by ~2×. **No capacity conclusion drawn in the archive is currently valid.**

## 6. Kill switch / circuit breakers

| Control | Status |
|---|---|
| Kill switch fail-closed default | **Correct.** `risk.rs:450 load_or_default` → Triggered/Halted on empty store. Verified: `trading_state=Halted kill_switch=Triggered` before *and* after `start()` |
| Kill switch on Critical drift | **Wired** — `engine.py:1377-1385` |
| Circuit breaker (10/s, 100/min, 3 errors) | **Wired** — all three call sites present |
| Reconciliation-first recovery | **Wired but the CLI is broken** — `cli.py:127` `TypeError` |
| Dual authorization | **Weaker on release** (R5) |
| Recovery on empty store | `ADR-020` semantics exist; `restart.py:121` signature mismatch (B18) |

**This is the strongest subsystem in TITAN and it is genuinely fail-closed.** It should be
preserved exactly as-is.

## 7. Verdict

| Question | Answer |
|---|---|
| Are risk controls too weak / too restrictive / correctly wired? | **Appropriate in design, correctly wired, never exercised.** |
| Are they unintentionally preventing valid strategies from expressing edge? | **No — provably not.** Zero orders placed. |
| Could they be preventing edge without detection? | **YES — R7.** The backtest has no risk layer, so a gate-rejected strategy backtests green. This is the real version of the audit's question, and it is unanswerable today. |
| Is the risk system the bottleneck? | **No.** The Rust kernel is the best code in the repo. The bottleneck is the research instrument and the fact that the runtime cannot start. |
| Is the portfolio layer the bottleneck? | **No** — but it is the largest genuine underbuild, and it will become the bottleneck the moment a second strategy survives. |

**Do not weaken any risk control.** There is no evidence they cost returns, and the evidence
that they are correct is strong. The one thing to **add** is the constrained-vs-unconstrained
backtest (R7), which would finally let the question be asked.
