# TITAN NEXT ACTIONS — 2026-09-29

The smallest set of changes with the largest verified improvement. Not a 100-task roadmap.
Every item: WHY NOW / PROBLEM ADDRESSED / EXPECTED EFFECT / DEPENDENCIES / COST / RISK /
TEST / SUCCESS CRITERIA / ROLLBACK.

---

## FIX NOW (unblocks everything; ~1-2 weeks)

### F1. Complete the promotion→certificate→paper seam
- Change: PromotionGate.promote() (or an explicit, scoped, logged dev-cert flow) issues a
  real Ed25519 certificate; paper_session.py calls initialize_new_session before the loop;
  ReplayEngine gets a working cert path (or routes through the harness).
- WHY NOW: it is the single failure that makes paper trading and engine backtests
  structurally impossible (engine.py:886-895 vs bridge.py:34 vs promotion.py:508-529).
- PROBLEM ADDRESSED: root cause #2 — the dead research→operation loop.
- EXPECTED EFFECT: a paper session that actually submits, fills, reconciles; shadow-trade
  evidence becomes collectable (the promotion gate's ≥5-shadow-trades requirement stops
  being structurally unsatisfiable).
- DEPENDENCIES: none (all pieces exist; only wiring missing).
- COST: ~2-3 days + tests.
- RISK: low — cert gate is already default-deny; issuance only widens the path to
  paper (no live capital exists anywhere).
- TEST: extend tests/e2e/test_profit_engine_e2e.py pattern to scripts/paper_session.py on
  SimulatedAdapter; assert ≥1 accepted order, InSync reconciliation, kill-switch release
  flow.
- SUCCESS: a scripted paper session completes orders and writes shadow events to the DB.
- ROLLBACK: revert wiring; gate remains default-deny.

### F2. Honest test architecture
- Change: invert conftest.py:76-85 — real submit_intent by default; bypass becomes an
  opt-in fixture for pre-gate unit suites only; add a nightly/CI job running ReplayEngine
  and paper_session against the UNPATCHED engine.
- WHY NOW: the suite is green while every production entrypoint crashes; no regression can
  be detected until this changes.
- PROBLEM ADDRESSED: false confidence; wheel-vs-src drift precedent.
- COST: 1-2 days (fix the handful of tests that genuinely need the bypass).
- TEST: the new CI job is the test.
- SUCCESS: a break like B1/B3 turns CI red.

### F3. Correctness fixes (B4, B5, B6, B7)
- Change: fill-delta→cumulative restore semantics (engine.py:365-370); broker sync side
  vocabulary + cash accounting + shorts (290-328); carry trailing state across bars
  (backtest/engine.py:134-143); gap checks against eff_stop (147-171).
- WHY NOW: restart corruption and phantom stop behavior invalidate any paper/backtest
  result the moment F1 lands.
- COST: ~3-4 days with the 3 economic regression tests from TEST_EFFECTIVENESS_REPORT.
- TEST: multi-poll partial fill + restart → identical position/cash; broker-held long+short
  at start → correct portfolio; trailing stop ratchets across ≥3 bars.
- SUCCESS: tests pass against real engine semantics.

### F4. Canonical cost model + kill the two miswires
- Change: one cost object (spread+commission+min-fee) consumed by harness AND engine AND
  paper fills (replace fees=0 at engine.py:736); fix paper_session.py gross-cap=1× and
  papertrade.py daily-loss-as-gross-exposure miswires.
- WHY NOW: four divergent cost semantics + cost-free paper fills guarantee paper results
  will overstate; the miswires silently cap any future session.
- TEST: paper fill fees equal promotion-evidence fees for identical trades.
- SUCCESS: one number for "cost of a round trip" everywhere.

## RESEARCH NEXT (immediately after F1-F4; ~2-4 weeks)

### R1. Re-pull and verify the free FX data (Dukascopy 1m bid/ask, multi-year 1h/4h)
- PROBLEM ADDRESSED: the only surviving candidate (traderdev F1-4h) and the entire
  cost-fidelity line (EXP-00019/25/26, P4) are unvalidatable on midpoint data; the prior
  pull failed contract (56.94%/99.59% missing) and was shelved instead of fixed.
- EXPECTED EFFECT: measured spreads replace assumed 0.10/0.50 bps; a VIRGIN 12-month
  window exists for the candidate.
- COST: time + disk (scripts already exist: scripts/pull_dukascopy_1m.py).
- TEST: data_quality_audit.py passes; window verified complete vs contract before use.
- SUCCESS: candidate re-run on fresh window with measured costs → a defensible promote or
  a sealed reject. Either outcome is progress.

### R2. Enforce the freeze in code
- Change: dataset fingerprint + gate refusal for experiments targeting the exhausted
  2025-08..2026-07 window.
- WHY NOW: ADR-026 was violated (EXP-00031); policy-only freezes have already failed once.
- **RATIFIED 2026-09-29 (maintainer decision):** no re-run of any experiment — including
  EXP-00022 and the 15-concept screen — may target the 2025-08→2026-07 window. Every result
  computed on it is void and inadmissible as evidence. This corrects the secondary audit's
  original item #9, which proposed "windows unchanged"; the corrected text lives in
  `secondary/TITAN_NEXT_ACTIONS.md` §9/§9b. The re-run plan for EXP-00022 drops the frozen
  year from the 8y series; F1@4h verdict re-run requires **≥12 fully virgin years** at census
  alpha (t ≥ 3.90, net Sharpe ≥ 1.15); a virgin 12-month span is **diagnostic-only**. Ruled by
  the 4-agent council 2026-09-29 — see `DEBATE_RE-RUN_PROCEDURE.md`.
- COST: <1 day.

### R3. Cross-sectional equities/FX screen on ≥10 names / ≥6 pairs
- PROBLEM ADDRESSED: the largest untested hypothesis class (only 1-2 pair tests so far).
- COST: a script in the existing harness; yfinance already wired for universes.
- SUCCESS: IC-based screen with the existing gates; promote-or-seal, nothing in between.

## BUILD LATER (only on triggers)

| Item | Trigger |
|---|---|
| Wire HRP/ensemble allocators + portfolio WFO/CV (skfolio methodology) | ≥2 qualified strategies |
| LOB execution simulation (hftbacktest-style) | a microstructure hypothesis survives a real-data screen |
| MTF runtime, Monte Carlo, observability stack | the single-TF paper loop has run ≥1 real session |
| Any LLM/agent capability beyond ADR-007 | adopt only the 2026 evaluation checklists (point-in-time, cost/turnover, artifact release) — external evidence shows no public LLM trader with verified profitability |

## DO NOT BUILD (ever, absent new evidence)

- More strategies of the exhausted classes (absorbing exclusions stand).
- More governance documents without wiring.
- More AI infrastructure as a substitute for the seam fix.
- Live-capital authority in any form until a strategy passes the gate on virgin data with
  measured costs AND ≥5 shadow trades of paper evidence.

## The single experiment that would most reduce uncertainty

Run traderdev-ema9-vwap 4h on a NEW 12-month Dukascopy bid/ask window with
measured spreads and canonical costs, pre-registered (same protocol as EXP-00031 but with
a genuinely untouched window). Outcome A (survives): TITAN has its first defensible
candidate and the promotion pipeline gets exercised end-to-end for the first time.
Outcome B (fails): the last marginal candidate is sealed, and the project can honestly
decide whether the remaining hypothesis space (cross-sectional, microstructure) justifies
the data investment. Either outcome converts the current uncertainty into a decision.

---

# SECOND-AUDIT ADDENDUM — corrections to the plan above

Produced by a second, independent audit of the research path. **It corrects the plan above in
one place and adds five gates it omits.** Full evidence in `TITAN_PROFITABILITY_FORENSICS.md`
addendum and `BUG_AND_RELIABILITY_REPORT.md` §1b.

## CORRECTION — the freeze must be a virgin window, and the F1@4h cell is the target

The plan above already requires *"a genuinely untouched window"* for the decisive experiment
and already lists R2 (enforce the freeze in code). That is correct and must not be softened.
**This addendum strengthens the correction in two ways:**

1. **A diagnostic re-run on the known window is still worth doing — but it is a *diagnostic*,
   not a verdict.** Its purpose is to answer "did the instrument repairs work?", e.g. does
   EXP-00022 now return Sharpe 0.48 as predicted? Its answer is **not admissible as a verdict**
   on that window, because ~546 trials have already been run against it and
   `ema9vwap_parameter_surface.py` alone contributed 198 correlated cells.
   **Separate the two questions: instrument validation on the known window, edge verdict on a
   virgin window. Never both on one.**
2. **The target is now specific and is not a guess.** `EXP-00025`'s committed artifact shows
   F1_ema9_vwap at 4h is **positive on EURUSD (+71.8 pips / 84 trades) and GBPUSD (+336.5 pips /
   79 trades) simultaneously**, while **all twelve 1h cells are negative**. TITAN's own memo
   already labels it *"CANDIDATE"*. It was closed by EXP-00031 — a long-only, differently-
   parameterised artifact producing 54 records where the original produced 163.
   **Pre-register this exact family, unchanged parameters, on a window no experiment has seen.**

## Missing gate A — an `UNDERPOWERED` verdict · 2 hours · **highest information-per-line change**

```python
se_sharpe = sqrt((1 + 0.5 * sharpe**2) / T_years)     # Lo (2002)
if se_sharpe > 0.5:
    verdict = "UNDERPOWERED"      # NOT "negative_result"
```

- **WHY NOW:** SE(SR) ≥ 1/√T **regardless of trade count**. At T = 0.41 yr, SE = 1.56; at
  T = 2 yr, SE = 0.94. **A true Sharpe of 1.0 and a true Sharpe of 0.0 are indistinguishable on
  this evidence.** 17 of 21 archived results are unmeasured, and all 17 are filed as rejections.
- **PROBLEM ADDRESSED:** the ledger currently mislabels ignorance as refutation.
- **EXPECTED EFFECT:** EXP-00031, EXP-00027, EQ-001/003/006/007/008 and the whole FX 4h axis
  are reclassified correctly. **This invalidates the headline "0/40" — which is the point.**
- **DEPENDENCIES:** none. **COST:** 2 hours. **RISK:** reputational, not technical.
- **TEST:** a synthetic SE=1.56 result must return `UNDERPOWERED`.
- **SUCCESS:** no experiment can be recorded as `negative_result` while SE(SR_ann) > 0.5.
- **ROLLBACK:** one branch.

## Missing gate B — DSR / PBO / trial ledger · 1 day · **an import, not a build**

- **Change:** vendor `HKUDS/Vibe-Trading/agent/src/quantlib/` (DSR, PSR, E[max N], BH-FDR, PBO,
  purged/group-purged/walk-forward/CPCV, `detect_boundary_leakage`, with a 336-line leakage
  test suite). **Or** `vectorbt/returns/metrics.py:19 deflated_sharpe_ratio` — ⚠️ read open PRs
  **#872 (kurtosis convention)** and **#873 (expanding minp)** first; a wrong kurtosis convention
  silently inflates DSR.
- **WHY NOW:** `validator.py:271` computes the Bonferroni and **discards it**; ~546 trials were
  evaluated at α=0.05 against a correct family-wise **9.2×10⁻⁵**. The 198-cell surface reports
  **no significance statistic at all** (`sharpe_from_pnl` multiplies by a function that returns
  1.0, is never called, and its t-stat is never written out). `knowledge/experiments/` is empty.
- **EXPECTED EFFECT:** DSR becomes the reported statistic; **N** becomes recorded data.
- **COST:** 1 day + licence check. **RISK:** medium (licence).
- **TEST:** the vendored leakage suite must pass unmodified.
- **SUCCESS:** every new experiment reports DSR, PBO and N.
- **ROLLBACK:** revert the gate wiring; the import is additive.

## Missing gate C — fix the two screen defects that void a third of the evidence · 1 day

- `scripts/screening/screen.py:40-61` — allow exits. **Verified: `results.json` has
  `"trades": 1` in every cell.** The "0/15 concepts" row of the terminal report is void.
- `replicated: bool = False` default in all six screen modules — **never `True` in production.**
  **Verified: CRYPTO-001 passed 4/5 gates; EQ-007 passed 5/9 including OOS Sharpe 1.249.**
  Zero survivors is currently a **constant**.
- **CHANGE:** delete the default; absent replication must return `INCONCLUSIVE`, not
  `negative_result`. Reclassify CRYPTO-001 and EQ-007 immediately.
- **COST:** 1 day. **SUCCESS:** no screen can return `negative_result` without a real
  replication flag; the 15 concepts re-run at >50 trades.

## Missing fix D — make `fees=0` paper fills impossible · part of F4, elevated

- `engine.py:736` builds fills with `fees=Money("0", ...)`. **Any paper session would overstate
  results by the full cost.** This is the single cheapest high-impact defect in either audit.
- **SUCCESS:** `engine.py` and `promotion.py` cannot disagree about the cost of a round trip.

## Missing fix E — absolute-value economic assertions · 1 day · ~50 LOC

Mutation testing (20 mutants, full suite): **8 killed, 6 survived** — `abs()` on Sharpe,
`profit_factor` → `100.0`, drawdown sign inverted, `sqrt(252)`→`sqrt(12)` (Sharpe off 4.6×),
`sqrt(252)`→`sqrt(52)` (vol off 2.2×), and `dual_ma` hardcoded to `"BUY"`.
**`promotion.py:488,494-495` consumes exactly these fields.** Exactly **one** test in 1180
asserts an absolute PnL value.

- **CHANGE:** one hand-computed fixture (known return series → exact Sharpe/DD/PF/vol) plus a
  strategy invariant (a symmetric input sequence must produce both BUY and SELL).
- **SUCCESS:** 12 of 12 mutants killed.

## Reordered priority

The merged order is F2 → D → C → F4 → A → B → E → F1 → F3 → R1 → R2 → R3.
**F2 (honest tests) and D (`fees=0`) first** — they are a one-hour deletion and a one-line fix
respectively, and until they are done every other fix is unverifiable.
**Gate A (`UNDERPOWERED`) before any re-run** — otherwise the re-run produces a verdict the
ledger cannot legitimately record.

## DO NOT BUILD — additions

- **A re-run on the exhausted 2025-08→2026-07 window as a *verdict*.** Diagnostic use only.
  This is the multiple-testing error the audit condemns, and EXP-00031 already committed it.
- **`sqrt(252)` on per-bar returns** in any new code path.
- **Any new screen module with its own cost model or drawdown function.**
MDEOF_MARKER_UNUSED

