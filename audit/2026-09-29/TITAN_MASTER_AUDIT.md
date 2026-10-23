# TITAN MASTER AUDIT — 2026-09-29

Hostile institutional review of Project TITAN.
Scope: full forensic inspection of /mnt/shared/projects/Trading/Project-TITAN (Rust core +
~400 Python files, 1180-test suite run green 2026-09-29), plus current (2026) GitHub
ecosystem research verified via GitHub/PyPI APIs same day.
Companion files: the 19 other reports in this directory. This file answers the questions.

---

## WHAT IS TITAN TODAY?

A research-governance platform with a small, real Rust authority core (risk, orders,
portfolio, reconciliation, event store), an honest ~40-experiment negative-result record
across FX, crypto, equities and gold, a fail-closed promotion gate that has correctly
refused to promote anything — and a trading loop that is broken at its single most
important seam: no production path can obtain an execution certificate, so paper trading
and engine-based backtesting crash before the first order (engine.py:886-895 vs
bridge.py:34; promotion.py:508-529 writes DB rows, never certificates).

The five-layer split:
- ARCHITECTURE: strong (single Rust authority, fail-closed defaults, deterministic events).
- IMPLEMENTATION: mixed (core real and wired; admission seam unimplemented; 4 divergent
  fill/cost models).
- VERIFICATION: misleading (1180 green tests mask production crashes via conftest.py:76-85).
- OPERATION: non-existent (no session has completed an order in the current code state;
  ops scripts hardcode a Windows machine).
- ECONOMIC USEFULNESS: zero as a trading system today; high as an honest research record.

## WHAT WAS TITAN SUPPOSED TO BECOME?

Per its ADRs and ARCHITECTURE.md: a deterministic, replayable, fail-closed platform that
discovers hypotheses, validates them under realistic costs with pre-registered OOS
discipline, promotes survivors through a multi-gate qualification pipeline, executes them
on paper via certified brokers (IBKR TWS), reconciles broker state against its own
portfolio, and feeds measured results back into research — while an AI layer stays
advisory. In intent it is the same architecture NautilusTrader v2 is now converging on
(Rust core, backtest/live parity, venue reconciliation).

## WHERE DID THE PROJECT DEVIATE?

1. It built the entire research→execution pipeline EXCEPT the arrow that connects them
   (certificate issuance + session init + research feedback). Default deny with no path to
   yes.
2. It verified each half in isolation — the test suite bypasses the gate the production
   path crashes on (conftest.py:76-85) — so the halves never had to meet.
3. It kept researching after proving its hypothesis space empty: the alpha-search terminal
   report, the pivot decision, and ADR-026's data freeze were all written, then the
   exhausted 2025-08..2026-07 window was reused post-freeze (EXP-00031's "OOS" lies inside
   the tuning-seen range).
4. It spent the surplus effort on spec-first layers (memory, features, MTF runtime,
   portfolio combinators) that nothing imports, while the seams that matter went
   unbuilt and data re-pulls were shelved after one failed attempt.

## WHAT DOES TITAN DO BEST?

1. Honest, cost-aware negative research: ~40 pre-registered experiments, absorbing
   negative-result seals, and the willingness to kill its own promotion (EXP-00017's 2-fold
   OOS retest) — a standard almost no open-source project meets.
2. The Rust authority core: dollar-based gross exposure, order state machine, append-only
   event store, reconciliation-gated kill switch — correct, wired, and tested (including
   an exact-$10M-limit end-to-end rejection).
3. Fail-closed recovery: HALTED restore on empty state, Unknown-order resolution via
   idempotency keys, two-person release with nonce replay protection.
4. Economic honesty about its own numbers: it publicly disclaimed its gate's own
   drift-inflated Sharpe series (ema9vwap_promotion_report.md:34-41).

## WHAT DOES TITAN DO POORLY?

1. Integration at the seams (promotion→certificate→paper→feedback).
2. Verification honesty (test suite validates a bypassed path).
3. Execution-economics measurement (assumed spreads, fees=0 paper fills, no fill audit).
4. Restart/state correctness (fill-delta restore bug, broker-sync crash, sim restore stub).
5. Data operations (corrupt FRED files committed, one failed Dukascopy pull shelved).
6. Documentation hygiene (runbooks and phase-j docs reference behavior and classes that do
   not exist).

## WHAT IS ACTUALLY BROKEN? (top verified items)

- B1/B3 (CRITICAL): cert-gate crash kills ReplayEngine backtests AND paper sessions.
- B4 (HIGH): crash-restart double-applies partial fills (delta vs cumulative).
- B5 (HIGH): start(sync_from_broker=True) crashes on broker-held positions; cash
  double-counts; shorts skipped.
- B6/B7 (HIGH/MED): trailing stops don't ratchet across bars; gap checks test the wrong
  price.
- B8 (MED): wall-clock daily-loss gate silently rejects intents in multi-month backtests.
- B9 (MED): risk-token secret is a public constant — token provides no integrity.
- Plus 2 config miswires ($5,000 gross cap in papertrade.py; 1× capital cap in
  paper_session.py) and L1-L5 (price-less fills, nonce TOCTOU, float money, cash
  self-comparison, expired-order poll leak).

## WHAT IS ONLY DOCUMENTED?

Multitimeframe runtime ("NOT STARTED"), Monte Carlo, stop/TP/trailing orders at execution,
the feature-graph layer, the memory/AI subsystem, the data freeze, net/sector/volatility
risk limits, and the runbook's "System state: ACTIVE" paper session.

## WHAT IS NOT MAKING A DIFFERENCE?

The AI layer (advisory policy exists; nothing imports the code), the observability stack,
the MTF runtime, portfolio combinators (0 qualified strategies), the Fincept integration
(scaffolding), and the Windows ops scripts.

## WHY ARE CURRENT STRATEGIES NOT PRODUCING USEFUL RESULTS?

Because the searched strategy space demonstrably contains no post-cost edge at retail
cost levels — and the platform cannot currently search the adjacent spaces. Evidence,
not opinion:
- FX: expected edge 0-2 pips < spread 0.6+ pips + $2/side commission floor
  (WHY_OUR_FOREX_SYSTEM_IS_NOT_CREATING_ALPHA.md:7); 0/15 screen concepts survive
  ≥200 pips/yr; the one promoted effect failed its own OOS retest.
- Crypto: maker fee ≈ 40× the harvestable half-spread (CRYPTO-005); net edge -2.02 to
  -2.04 bps/fill; 0 trades for OFI at retail latency.
- Equities: best OOS Sharpe 1.2485 (EQ-007 PEAD) fails its own rank-IC/turnover gates;
  EQ-Micro-001 OOS Sharpe -32.47.
- Gold/macro: P2 FAIL (3/4 kill criteria); regime gating DEGRADED the tested strategies
  (EXP-00015: 0.73 vs 3.76).
- The single net-positive candidate (traderdev F1-4h: +71.8/+336.5 pips/yr) fails the
  gate 4/7 and cannot be re-validated on fresh data — none exists in the repo.

## IS THE PROBLEM DATA, STRATEGY, VALIDATION, EXECUTION, RISK, PORTFOLIO, INFRASTRUCTURE, RESEARCH, OR SOMETHING ELSE?

Ranked, with evidence:
1. **EDGE (strategy class × costs)** — primary. The searched space is empty at retail
   costs, proven honestly ~40 times.
2. **THE SEAM (integration/infrastructure)** — the promotion→certificate→paper→feedback
   loop is unimplemented, so the system cannot learn from operation. This is "something
   else": not missing technology, missing wiring.
3. **DATA** — blocks validation of the one surviving candidate and the next strategy class
   (no multi-year 1h/4h, no measured bid/ask, 6 corrupt FRED files).
4. **VALIDATION** — leaks in both directions: Path-1 can QUALIFY on weak thresholds
   (false positives); the strict gate's shadow-trade requirement is structurally
   unsatisfiable and its cost-free series is drift-dominated (false negatives); the freeze
   is unenforced.
5. **EXECUTION ECONOMICS** — unmeasured (assumed spreads, fees=0 paper fills).
6. NOT the problem: RISK (correct-but-dormant; never blocked a strategy), PORTFOLIO
   (nothing to combine), the Rust/Python boundary, and AI absence.

## WHAT ARE THE TOP VERIFIED BOTTLENECKS?

1. No demonstrable post-cost edge in the searched hypothesis space (with the honest
   negative record as the proof).
2. The broken research→operation seam (certificate issuance, session init, research
   feedback) — the platform cannot currently produce the very evidence (shadow trades,
   measured fills) its own gate requires.
3. Data poverty for the next research class: no multi-year intraday FX, no measured
   spreads, exhausted 12-month window.
4. Validation credibility: same-bar fills, OOS→gate leakage, unenforced freeze, Path-1
   bypass.

## WHAT DO CURRENTLY ACTIVE GITHUB PROJECTS DO THAT TITAN DOES NOT?

- NautilusTrader (v2, Rust+PyO3, rc5 2026-09-15): ONE deterministic core for backtest,
  paper and live with venue reconciliation — the thing TITAN documents but hasn't wired.
- Qlib + RD-Agent (v1.0.0, 2026-09-23): an automated hypothesis→factor→backtest→feedback
  loop with point-in-time discipline — the research loop shape TITAN should benchmark.
- freqtrade (2026.8): a paper/dry-run loop that simply WORKS, with hyperparameter search.
- hftbacktest: LOB/queue/latency fill simulation (only if a microstructure hypothesis
  appears).
- skfolio: look-ahead-safe portfolio cross-validation (only after ≥2 qualified strategies).

## WHAT SHOULD TITAN ADOPT? ADAPT? REJECT?

- ADOPT: the 2026 LLM-trading evaluation checklists (point-in-time splits, explicit
  cost/turnover models, artifact release — arXiv:2605.19337, 2606.08285); Qlib-style
  point-in-time cross-sectional research patterns; the "one deterministic core" standard
  NautilusTrader v2 demonstrates (by finishing TITAN's own Rust core wiring, not by
  switching frameworks).
- ADAPT: TradingAgents' analyst/debate/risk-team structure and FinMem's memory taxonomy
  as RESEARCH TOOLING only; RD-Agent's factor-mining loop with TITAN's own gates;
  hftbacktest's fill model if a microstructure hypothesis survives.
- REJECT: any claim that LLM agents are a source of edge (2026 evidence: the AI-Trader
  live benchmark finds most agents lose money; 0/19 published studies reproducible;
  the two most-starred repos self-disclaim); vectorbt-pro commercial lock-in; RaptorBT as
  a vectorbt replacement until independently validated.

## WHAT SHOULD TITAN STOP BUILDING?

(Full list in TITAN_STOP_BUILDING.md.) Headline: more governance documents without wiring,
more strategies of the exhausted classes, more AI infrastructure, the Path-1 qualification
bypass, the dead memory/feature/MTF layers, and Windows ops scripts.

## WHAT SHOULD TITAN BUILD NEXT?

(F1-F4 in TITAN_NEXT_ACTIONS.md.) In order: (1) complete the certificate/session seam;
(2) make tests exercise the real path; (3) fix restart/stop correctness bugs; (4) one
canonical cost model + fix the two miswires. Then research: re-pull free FX bid/ask and
multi-year 1h data, enforce the freeze in code, run the first cross-sectional screen.

## WHAT EXPERIMENT WOULD MOST REDUCE UNCERTAINTY?

The pre-registered re-run of traderdev-ema9-vwap 4h on a NEW 12-month Dukascopy bid/ask
window with measured spreads and canonical costs. Survives → first defensible candidate
and the promotion pipeline runs end-to-end for the first time. Fails → the last marginal
candidate is sealed and the project decides, with evidence, whether the remaining
hypothesis space justifies the data investment. Either outcome converts the current
uncertainty into a decision.

---

## FINAL PRINCIPLE, APPLIED

TITAN does not currently possess a demonstrable trading edge — it possesses the proof of
that fact, which is rarer and more valuable than most projects' unverifiable claims. The
shortest evidence-backed path forward is not more AI, more strategies, or more
infrastructure: it is to finish the one seam that connects its excellent research loop to
its excellent execution core, feed the loop real (free) data it has not exhausted, and let
the gate keep doing what it does best — refusing anything that cannot survive honest
validation.
