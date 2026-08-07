# traderdev-ema9-vwap — Promotion-Gate Evaluation Report (ADR-022/023)

- **Strategy:** `traderdev-ema9-vwap` (EMA9 × VWAP crossover + ATR trailing stop)
- **Source:** trader.dev F1 family port (EXP-00025), registered candidate
- **Data:** real Dukascopy 1m bid/ask resampled to 4h (native TF), EURUSD + GBPUSD
- **Date:** 2026-08-07
- **Method:** `PromotionGate.evaluate()` against a **temporary** research DB seeded
  with real measured evidence. Read-only w.r.t. production research state; no
  promotion; no `QUALIFIED` status change.
- **Plan provenance:** multi-model debate (`plan_debate.py`, nemotron-3-ultra +
  minimax-m3 → antigravity-gemini-3.1-pro), Q1 = reduced 2D sweep, Q2 = option C
  (walk-forward honestly UNMET — only the tuning dataset exists).

---

## Verdict

**NOT QUALIFIED — 4 of 7 mandatory-or-evaluable gates fail (fail-closed).**
The candidate remains a registered candidate. Nothing in this evaluation
changes, and nothing will change until the failures below are addressed with
real evidence.

| Gate | Result | Evidence |
|---|---|---|
| base_qualification | ✅ PASS* | IS Sharpe 5.93 (see *caveat*) |
| walk_forward | ❌ FAIL | No walk-forward data (UNMET by design, Q2=C) |
| parameter_stability | ❌ FAIL | No plateau surface data (fragile surface shown below) |
| independent_replication | ✅ PASS* | corr 0.000, pSharpe 7.12 / rSharpe 5.93 (see *caveat*) |
| portfolio_impact | ✅ PASS | ΔSharpe +2.01, max_corr 0.000, DD contrib 1.7% (empty pool — trivial) |
| shadow_sufficiency | ❌ FAIL | 0 shadow trades recorded |
| shadow_performance | ❌ FAIL | 0 shadow trades |
| ensemble_regression | ✅ PASS | No qualified pool — nothing to regress (vacuous) |

\* **Honesty caveat on the two Sharpe-based PASSes.** The gate's
`_strategy_return_series` holds a long/flat position with **no costs, slippage,
or spread**, so its Sharpe measures directional market drift, not the
strategy's cost-aware edge. The EXP-00025 cost-aware harness (real spread +
slippage + commission, intrabar stops) measured the real edge at **+71.8 pips
(EURUSD) / +336.5 pips (GBPUSD) over 12 months** — a far more modest result.
The 5.93/7.12 Sharpes are inflated by the series construction and must not be
read as alpha.

---

## Per-gate detail

### base_qualification — PASS (artifact-inflated)
Gate threshold IS Sharpe ≥ 0.5. Real measured 4h IS Sharpe (cost-free series):
EURUSD 5.93, GBPUSD 7.13. But see caveat: this is drift-dominated. The honest
cost-aware pips are positive on both pairs but modest, and quarterly stability
was 2/4 (EUR) and 3/4 (GBP) in EXP-00025.

### walk_forward — FAIL (honest UNMET, per debated Q2 = option C)
The only dataset available is the same 12-month Dukascopy window the strategy
was tuned on. A 75/25 split of already-seen data, or rolling windows over it,
would be statistically dishonest — the gate would report a "walk-forward"
number that is not out-of-sample. Per the debate decision, `wf_sharpe` is not
seeded and the gate fails closed. **Requirement to unblock:** fresh
out-of-sample data (new history, or a live/paper observation period of 3–6
months) — nothing in the existing data can satisfy this gate honestly.

### parameter_stability — FAIL (surface measured: fragile)
The 2D sensitivity surface (ema_period 5–21 × trail_mult 2.0–3.0, 99 cells ×
2 pairs, cost-aware) shows:

| Metric | EURUSD | GBPUSD |
|---|---|---|
| Positive cells | 44/99 (44%) | 74/99 (75%) |
| Default-cell neighborhood (ema 7/9/11 × trail 2.0–2.2) | **3/9 positive, mean −203 pips** | 8/9 positive, mean +298 pips |
| Best cell | ema=13, trail=2.9 (+461 pips) | ema=7, trail=2.6 (+1,062 pips) |

Interpretation: the edge is **pair-specific and parameter-fragile**. On EURUSD,
moving ema 9→7 collapses the result from +72 to −438 pips — there is no compact
positive plateau. The two pairs favor *different* parameter corners, the
signature of pair-specific noise rather than a transferable edge. Even if the
DB stored plateau metrics (it does not — see structural note), this surface
would not clear a meaningful stability threshold. **Requirement to unblock:**
a genuinely stable, cross-pair plateau (or an honest explanation of why the
strategy is pair-specific by design).

### independent_replication — PASS (weak / artifact-inflated)
The live dual-run path used two real EURUSD/GBPUSD runs. Correlation 0.000
because replication_returns=None (the F1 anti-self-referencing guard) — i.e.
this PASS reflects scorecards, not a real return-correlation test. The
scorecard Sharpes are the same drift-dominated numbers above. **Requirement to
unblock:** a true independent OOS replication (fresh data), with return
correlation computed on real, cost-aware series.

### portfolio_impact — PASS (trivial)
ΔSharpe +2.01 against an **empty** qualified pool (max_corr 0.000, DD contrib
1.7%). First-strategy bonus — meaningless until there is a pool to correlate
against.

### shadow_sufficiency / shadow_performance — FAIL
0 shadow trades recorded in the research DB. The strategy must accrue
shadow-trade evidence (proposals in shadow mode, then paper) before these
gates can pass. This is the fastest actionable path: the F2 fix routes
candidates through the watchlist to produce shadow proposals — they need to
actually run and be logged.

### ensemble_regression — PASS (vacuous)
No qualified pool → nothing to regress against. Becomes meaningful only after
other strategies qualify.

---

## Structural findings (engineering debt surfaced by this evaluation)

1. **`set_qualification` cannot store plateau/replication/correlation metrics.**
   The `qualifications` table + `ResearchDB.set_qualification` expose
   backtest/wf Sharpe, returns, DD, paper_trades — but **no columns** for
   `plateau_stability`, `plateau_coverage`, `replication_sharpe`, or
   `max_correlation`. After ADR-023 (F3) removed the notes-string fallback,
   `_gate_parameter_stability` is **structurally unsatisfiable** through the
   sanctioned DB API: even a real ParameterSurface computation could not be
   persisted in a way the gate reads. This is a schema/API gap, not a strategy
   gap. Fix: extend the schema + `set_qualification` with these four columns
   (an ADR-tracked change).
2. **The gate's Sharpe series is drift-inflated.** `_strategy_return_series`
   (long/flat, no costs) should not be used to *pass* gates without a
   cost-aware companion. Recommend the gate accept a stored cost-aware Sharpe
   as the authoritative evidence rather than deriving one ad hoc.
3. **`gate.evaluate()` exceptions propagate** (F7) — a signal that raises fails
   the whole gate. Correct fail-closed behavior; noted for completeness.

---

## Honest recommendation

**Do not promote. Do not trade live.** The candidate:

1. Has no honest walk-forward evidence (and cannot get one from existing data),
2. Has a parameter-fragile, pair-specific surface (EURUSD neighborhood mean
   −203 pips; no shared best cell), and
3. Has zero shadow-trade history.

The EXP-00025 marginal edge (+72/+337 pips over 12 months at 0.1 lot) does not
survive the gate's evidentiary standards, and the gate's own Sharpe path
overstates it. This is the expected outcome per the evaluation brief: the value
is in the evidence, not a pass.

**What would change the verdict (in priority order):**
1. **Run it in shadow/paper** (watchlist routing already wired per ADR-022) and
   accrue real shadow trades → unlocks shadow_sufficiency/performance; after
   3–6 months of *fresh* paper data, walk_forward becomes satisfiable.
2. **Extend the qualifications schema** (plateau/replication/correlation
   columns) so parameter_stability can be evaluated at all.
3. **Investigate the pair-specific best cells** — if a regime gate (vol
   clustering, EXP-17) explains when EUR vs GBP works, that is a *new*
   hypothesis to test, not a reason to promote the base strategy.

**Verdict: CONTINUE RESEARCH (shadow evidence) — not promote, not retire.**

---

## Artifacts

- `research/evaluate_ema9vwap_gate.py` — Phase 1 gate diagnostic (read-only)
- `research/ema9vwap_parameter_surface.py` — Phase 2b 2D sensitivity sweep
- `research/results/ema9vwap_gate_diagnostic.json` — per-gate evidence
- `research/results/ema9vwap_parameter_surface.json` — 198-cell surface
- Plan: `~/hermes-plans/ema9vwap-gate-scope.md` (debated Q1/Q2 decisions)
