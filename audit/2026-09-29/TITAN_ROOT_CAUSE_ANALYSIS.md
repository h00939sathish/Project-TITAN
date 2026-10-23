# TITAN ROOT-CAUSE ANALYSIS — 2026-09-29

For each major failure: SYMPTOM → IMMEDIATE CAUSE → SYSTEMIC CAUSE → PROCESS CAUSE →
ROOT CAUSE. Then a single integrated causal chain.

---

## Failure 1: "The system makes no money"

- SYMPTOM: no live, paper, or even backtested strategy produces useful post-cost returns.
- IMMEDIATE CAUSE: every strategy family searched (FX directional/momentum/carry/session,
  crypto funding/OFI/spread-capture, equity factors, gold macro) nets ≈ 0 or negative
  after realistic costs. Evidence: ~40 experiments, 0 survivors; the one promoted effect
  (EXP-00017) failed its own 2-fold OOS retest; the one net-positive candidate
  (traderdev F1-4h: +71.8/+336.5 pips/yr) fails the gate 4/7.
- SYSTEMIC CAUSE: the searched edges are small (0-3 pips, or 0.1%/period gross) and the
  cost layer (spread 0.6+ pips, $2 commission floor, maker fees 40× harvestable
  half-spread in crypto) is comparable in size. On liquid OHLCV data at retail costs,
  these hypothesis classes have no harvestable surplus. This is a REAL result — the
  project proved it honestly (ALPHA_SEARCH_TERMINAL_REPORT.md:14-15).
- PROCESS CAUSE: the research program searched ONE corner of hypothesis space (single-pair
  / single-market directional-regime-macro signals on one 12-month window of midpoint
  data) and then KEPT searching it after its own data-freeze decision (ADR-026 violated by
  EXP-00031; EXHAUSTION_MEMO's "tuning-seen" warning ignored).
- ROOT CAUSE: **no demonstrable edge exists in the searched space, and the platform was
  never able to test the adjacent spaces** (cross-sectional, microstructure-with-real-spreads,
  multi-year horizons) because of data poverty and a broken promotion→execution loop.

## Failure 2: "Paper trading produces nothing"

- SYMPTOM: paper sessions never produce orders, fills, or research feedback.
- IMMEDIATE CAUSE: `scripts/paper_session.py` never calls `initialize_new_session`
  (fail-closed HALTED) AND the first trade intent crashes the process at the certificate
  gate (bridge.py:34 "dummy_cert_for_paper_session" vs engine.py:886-895).
- SYSTEMIC CAUSE: the admission contract (default-deny certificates, ADR-028) was built
  with no issuer in production — `PromotionGate.promote()` writes a DB row, never a
  certificate (promotion.py:508-529); `create_signed_certificate` is called only from
  tests. Default deny with no path to yes.
- PROCESS CAUSE: the seam between "research" and "execution" was never integration-tested
  honestly — the conftest monkeypatch (conftest.py:76-85) let both halves develop against
  a bypass, so neither half ever had to meet the other.
- ROOT CAUSE: **the promotion→execution interface was designed, gated, and governed but
  never implemented end-to-end; verification was structured to hide exactly this.**

## Failure 3: "Backtests can't be trusted"

- SYMPTOM: engine-based backtests crash (cert gate) or produce optimistic results
  (EXP-00020: +6.25 pips/trade in-sample vs -20.00 real-engine).
- IMMEDIATE CAUSE: ReplayEngine defaults (0.0/0.0 bps costs, same-bar close fills,
  engine.py:81-83, 294→306) + the cert crash + OOS leaking into the stability gate
  (qualification_pipeline.py:209-225 → plateau_detector.py:41-43).
- SYSTEMIC CAUSE: four divergent fill/cost semantics; two qualification authorities
  (Path-1 script can QUALIFY on IS Sharpe ≥0.5/OOS ≥0.0; the strict gate has vacuous
  replication/portfolio checks in practice); no canonical cost object.
- PROCESS CAUSE: validation rules (ADR-031 no-same-bar-fill, ADR-026 data freeze) exist as
  documents, not code — nothing enforces them, and post-freeze work reused the exhausted
  window (EXP-00031's "OOS" lies inside the tuning-seen range).
- ROOT CAUSE: **validation discipline was treated as a documentation problem instead of an
  enforcement problem** — the gates can be gamed (false positives) and the freeze can be
  ignored (false confidence), in both directions.

## Failure 4: "The AI layer does nothing"

- SYMPTOM: ADR-007, vector memory, agent tooling — all present in docs, none in runtime.
- IMMEDIATE CAUSE: memory subsystem imported by nothing; feature graph test-only.
- SYSTEMIC CAUSE: AI was built spec-first as a governance exercise while the system it
  would advise had no working trading loop to advise.
- PROCESS CAUSE: building AI-adjacent infrastructure (memory, distillation, MCP bridge)
  before the base loop worked — architecture as procrastination.
- ROOT CAUSE: **premature construction of an advisory layer for a loop that did not exist.**
  (External 2026 evidence independently shows no public LLM trading system has verified
  profitability — so nothing of value was lost, but the pattern is diagnostic.)

## Integrated causal chain

```
Research optimized for GOVERNANCE and HONEST REJECTION
        │
        ├─► proved the searched strategy space empty at retail costs (a real result)
        │
        ├─► but searched only one corner of hypothesis space, on 1 year of midpoint data
        │
        ├─► and never built the seam that converts research into operation:
        │      promotion → certificate → paper → measured execution → feedback
        │      (cert issuer absent; entrypoint unwired; tests masked the gap)
        │
        └─► so the system cannot LEARN from operation, cannot validate its one
              surviving candidate on fresh data, and cannot measure real costs
              ───► no useful trading results
```

## The bottleneck, stated plainly

**The bottleneck is not AI, not Rust, not strategy ideas, not risk controls. It is the
broken research→operation seam** (certificate issuance + session init + honest tests +
research feedback wiring), **compounded by data poverty** (no multi-year 1h/4h, no real
bid/ask spreads) **that blocks validation of the only surviving candidate and the only
untested strategy class** (cross-sectional). Fix the seam, re-pull free data, and TITAN
becomes what it was designed to be: a machine that discovers, validates, executes, and
learns from genuine edge — or honestly proves there is none left to find.
