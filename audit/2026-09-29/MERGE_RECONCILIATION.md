# MERGE RECONCILIATION — two independent audits of Project TITAN

**Date:** 2026-09-29. This file consolidates two independent, same-day audits:

| Audit | Location | Size | Author |
|---|---|---|---|
| Primary | `audit/2026-09-29/` (this directory) | 20 reports | qoder |
| Secondary | `audit/2026-09-29/secondary/` (verbatim copy; originals at `research/audit/`) | 20 reports, 3,538 lines | maintainer |

The secondary audit was **copied, not moved** — the originals in `research/audit/` remain
the maintainer's and are leased to the opencode agent. The only edits made to the secondary
copy are the two window corrections ratified below (§5).

Both audits were conducted blind of each other and converge on the same central finding;
they differ in where the evidence is strongest. This file registers both.

---

## 1. Convergence (both audits, independently confirmed)

1. **TITAN has no demonstrable post-cost edge today.** Nothing in the archive survives
   both audits' scrutiny as a real, significant, correctly-costed result.
2. **The runtime cannot trade.** The certificate admission gate (default-deny, Ed25519)
   crashes every entrypoint; no production certificate issuer exists; paper/backtest/promotion
   all hit the same seam.
3. **The test suite's 1180 passes are partly a mask.** The autouse conftest monkeypatch
   replaces `submit_intent` so the certificate gate is never the tested path.
4. **The evidence base is not trustworthy as published.** Measurement defects (2× PnL
   double-count, long-only harness, sqrt(252) on per-bar returns, 10 bps ≠ 1 pip, bar-count
   power gates, crypto simulator with zero price PnL) void specific numeric conclusions.
5. **The ~40-experiment negative record is inadmissible in its current form** — neither
   citable as "0/40 concepts disproven" nor convertible into the positives it contains
   (EXP-00022 t=2.67, EQ-007 OOS Sharpe 1.249). See contradiction register §4.1.
6. **Preregistration is decorative.** Thresholds are invented at evaluation time (C15);
   preregs and results share one commit with no timestamp (C48); failed gates are invisible
   to the decision function (C3).
7. **Governance is aspirational, not enforced.** ADR-026's data freeze was violated by
   EXP-00031; the promotion gate is bypassable via Path-1 direct DB writes; dual authorization
   is weaker on release than on init (C20).
8. **The Rust kernel is the strongest part of the system.** Mutation testing (secondary
   audit) killed 8/8 risk/execution/fill mutants; both audits found the kernel, risk gates,
   and fill layer genuinely protected.
9. **The weakest parts are the strategy-signal layer and the performance-metric layer** —
   6/6 dangerous mutants survived there (hardcoded BUY, inverted drawdown sign, abs() on
   Sharpe, profit_factor=100.0, sqrt(252) variants). ~0% effective coverage exactly where
   profitability is decided.
10. **The shortest path to an honest answer:** fix the measurement instrument first
    (cost units, harness, Sharpe annualization, power gates), then re-run the 1–2 surviving
    candidates **on virgin windows** with preregistered, binding thresholds. Both audits'
    action plans reduce to this, in different orderings.

## 2. Where each audit is stronger

**Secondary audit is stronger on (adopted as authoritative):**
- Mutation testing programme (20 mutants; killed/survived lists, §6.4 of the primary
  BUG_AND_RELIABILITY_REPORT.md).
- Lo (2002) power analysis — SE(SR_ann) ≥ 1/√T; the F1@4h cell is UNDERPOWERED, not
  refuted; no `UNDERPOWERED` verdict class exists.
- The 546-trial census and the discarded Bonferroni correction (C10).
- The measurement-defect forensics: C1 (one trade per hypothesis), C2 (replication gate
  constant-false), C4 (cost units), C5 (long-only harness), C6 (2× PnL), C7 (fake
  walk-forward), C8 (sqrt(252)), C11 (bar-count gate), C12 (impossible Sharpe 19–21),
  C14 (crypto zero price PnL), C15 (invented prereg thresholds).
- The dead-subsystem census: C22–C48 (decision traces, schemas, Prometheus metrics,
  vector memory, fabricated MCP strategy names, impossible archived metrics).
- The artifact-level forensics (B1–B24/D1–D5 in their forensics report; EXP-00025 24-cell
  artifact; EXP-00031 non-reproduction).

**Primary audit is stronger on (adopted as authoritative):**
- The Rust boundary verdicts and the admission-seam anatomy (engine.py:886–946, the exact
  crash chain, the three entrypoints that hit it).
- The two risk miswires: `papertrade.py:49-59` (daily_loss_limit passed positionally as
  max_gross_exposure) and `paper_session.py:540-550` (gross cap = 1× capital).
- **The free-paper-fill defect** (`engine.py:736` `fees=Money("0")`) — paper sessions trade
  cost-free, so no paper result is comparable to promotion evidence. (One of the four the
  maintainer flagged as missed.)
- Restart/concurrency internals: fill-delta vs cumulative restore (B4), `start()` broker-sync
  crash + cash double-count + shorts skipped (B5), nonce TOCTOU (L2), wall-clock daily-loss
  window in backtests (B8).
- The qualification-authority conflict: PromotionGate (fail-closed) vs Path-1 direct-DB
  bypass (`qualification_pipeline.py:479-488`) vs ADR-022.
- Environment drift: Python 3.14/3.12/cp313 mismatch, Windows paths in shell scripts,
  rustup/cargo absent so the `.so` cannot be rebuilt.
- The per-suite test inventory and the conftest fixture's exact mechanism (autouse,
  node-id filter).

**Four confirmed bugs in the primary audit that the secondary audit missed**
(the maintainer's count; the free-paper-fill defect was the one named):

1. Free paper fills — `engine.py:736` `fees=Money("0")`.
2. `papertrade.py:49-59` — daily-loss-limit positional miswire ($5,000 gross cap).
3. `paper_session.py:540-550` — gross cap = 1× capital.
4. `engine.py:365-370` — fill-delta vs cumulative restore on restart (B4).

## 3. Confirmed overlaps (same defect, found independently)

| Secondary | Primary | Defect |
|---|---|---|
| C16 | B1/B3 | Certificate-gate crash kills every entrypoint; conftest masks it |
| §1 (fix list) | B2 | conftest.py:76-85 autouse monkeypatch |
| C21 | B9 | Hardcoded risk-token secret `TITAN_RISK_SECRET_KEY` |
| C18/C42 | environment finding | Windows paths in shell scripts on a Linux checkout |
| C19 | H1 (now confirmed) | Correlation risk rule unreachable — runner writes `_last_prices` directly |

## 4. Contradiction register

### 4.1 The central dispute: "honest negative record" (primary) vs "measurement artifact" (secondary)

- **Primary (Cause A):** ~40 sealed negative experiments, consistent across asset classes,
  constitute a valid market finding — no post-cost edge in the searched space.
- **Secondary:** the instrument was broken (C4/C5/C6/C8/C11/C14/C15), so the 0/40 is a
  measurement artifact; several "negatives" are actually positive-or-unresolved when
  re-costed (EXP-00022 → +4.4–4.9%/yr Sharpe 0.48–0.54; F1@4h → UNDERPOWERED not refuted;
  EQ-007 → real OOS edge rejected on a coin-flip gate).

**RULING (both audits, adopted):** the secondary audit is right about the instrument, and
the primary audit is right about the breadth. Resolution:

- The **numeric** record ("0/40", per-experiment Sharpe/PnL figures) is **inadmissible as
  published** — the measurement defects are CONFIRMED and directionally mixed.
- The **qualitative** record (three asset classes, dozens of independent strategy families,
  no family surviving even a broken instrument that in several places *favored* survival —
  e.g. C13's lookahead, C38's overstated bars/year) is **suggestive but not probative**.
  It does not license "stop searching FX momentum/carry" as an absorbing conclusion.
- The correct state of the archive is: **"results pending re-measurement"**, not "0/40"
  and not "reopened". Both audits' plans now say exactly this: fix the instrument, re-run
  the survivors on virgin windows, promote or seal on the outcome.

### 4.2 Correlation risk rule — inert (secondary) vs unverified (primary H1)

**RULING:** secondary CONFIRMED — `paper_session.py:861` writes `_last_prices` directly,
`risk.rs:706` reads engine state, so the rule can never fire. Primary H1 upgraded to
confirmed (see §3). Fix: route through `engine.update_price()` or delete the rule.

### 4.3 conftest disposition — constrain/simplify (primary) vs delete (secondary)

**RULING:** delete (secondary §1 wins). The monkeypatch has already rotted once (it is the
only reason 1180 tests pass while the runtime crashes). A constrained variant keeps the seam
that failed. Deletion forces the real gate into the test path; the legitimate need it
served (tests without a certificate) must be met by a real, scoped dev-cert flow — which is
the same fix as the admission seam itself (secondary §2, primary fix-priority 1). One fix
serves both.

### 4.4 Monte Carlo — deferred (primary BUILD LATER) vs critical (secondary)

**RULING:** neither first. The secondary audit's own mutation results show the metric layer
has ~0% coverage; the highest-information fix is its §4 (one hand-computed fixture + one
strategy invariant), not Monte Carlo. Monte Carlo stays deferred until the metric layer is
fixture-protected — a sharper trigger than "runtime stable", aligned with the secondary
audit's "vendor the statistics layer" (§5) which the primary audit did not inventory.

### 4.5 Walk-forward — exists-but-unused (primary) vs fake (secondary C7)

**RULING:** secondary CONFIRMED. The harness's exported `walk_forward.mean_sharpe` is a
sliding same-params window with no training and no test partition; the genuine
`WalkForwardOptimizer` (`walkforward.py:130`) is unreachable from any experiment. The
primary audit's "WFO is implemented but unwired" understated the defect: the *wired* one is
a fake. Any re-run must either call `WalkForwardOptimizer` or stop exporting
`mean_sharpe` as walk-forward evidence.

### 4.6 Order of fixes — seam-first (primary) vs instrument-first (secondary)

**RULING:** both orders are correct and non-conflicting; they target different loops.
The secondary audit's items 1–8 (conftest, cert fix, measurement defects, fixtures,
statistics layer, UNDERPOWERED verdict, cost schedule, datasets) are all prerequisites for
its item 9. The primary audit's F1–F4 (seam, cost-model consolidation, promotion-gate
wiring, data pull) are the same work grouped differently. **Merged execution order** is
the secondary audit's numbering, with the primary audit's two risk miswires and the
free-paper-fill fix folded into its §2 (session/cert fix) — they are all part of "make the
runtime honest before running it".

## 5. Virgin-window ratification (maintainer decision, 2026-09-29)

The secondary audit's original item #9 proposed re-running EXP-00022 and the 15 concepts
with "parameters, data and windows unchanged". The primary audit established that ADR-026
froze the 2025-08→2026-07 window and EXP-00031 already violated that freeze.

**RATIFIED: no re-run may target the 2025-08→2026-07 window. Any result computed on it is
void and inadmissible as evidence.** Applied edits (the only content changes to the
secondary copy):

- `secondary/TITAN_NEXT_ACTIONS.md` §9 — "windows unchanged" replaced with a binding
  WINDOW CORRECTION block: EXP-00022 drops the frozen year from the 8y series; the
  15-concept screen gets a virgin Dukascopy span; the old `results.json` (C1) is discarded.
  Prediction table annotated: t=2.67 must be re-derived on the 7 pre-freeze years (n≈353);
  if that series alone cannot reach t≥2 the verdict is UNDERPOWERED.
- §9b — a binding **Window** row: virgin 12-month span only; the burned year settles
  nothing.
- Re-audit trigger — results on the frozen window do not count as a pass.
- `TITAN_NEXT_ACTIONS.md` (primary) R2 — the same rule ratified in the primary plan, with
  a pointer to the corrected secondary text.

## 6. Consolidated bottom line

TITAN is an **architecturally serious trading system with a broken measurement instrument
and an unwired admission seam**. It has never produced a trustworthy trading result in
either direction. The two audits disagree on nothing that survives contact with both sets
of evidence: the negatives are real but mis-measured; the positives are real but
mis-measured; the fix for both is the same — repair the instrument, freeze the windows,
re-run the survivors once, and let the outcome decide. Nothing about the merged record
supports adding strategies, AI, infrastructure, or data breadth ahead of that repair.

## 7. Layout map

```
audit/2026-09-29/                      primary audit (20 reports, authoritative on §2-primary)
audit/2026-09-29/secondary/            secondary audit (verbatim copy + §5 window edits)
audit/2026-09-29/MERGE_RECONCILIATION.md   this file
research/audit/                        secondary audit originals (maintainer-owned, leased)
```
