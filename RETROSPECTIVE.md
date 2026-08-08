# Project TITAN — Retrospective

> Written at the close of the alpha-search phase (2026-08-08).
> Companion: [research/ALPHA_SEARCH_TERMINAL_REPORT.md](research/ALPHA_SEARCH_TERMINAL_REPORT.md)

## Timeline (compressed)

- **Design & architecture:** research-engine comparison, adoption decisions,
  ADR-001..; the "governed synthesis" constitution.
- **Infrastructure build:** Rust+PyO3 core (typed intents, event sourcing,
  risk state machine), Python strategy/research/backtest layers, IBKR paper
  adapter, promotion pipeline, kill switch, 807-test suite.
- **OHLC & exit-intent cycles:** OHLC wired end-to-end; stop/TP/trailing exit
  intents (ADR-021); promotion fail-closed (ADR-022/023).
- **First real validation:** promotion-gate evaluation of the EMA9×VWAP
  candidate → NOT QUALIFIED (4/7 gates).
- **Search expansion:** cheap wide screening (15 concepts → 0 survivors),
  cross-pair MR (non-cointegrated), carry (already rejected), multi-TF
  confluence (FAIL), gold macro-momentum (FAIL 3/4).
- **The honest end:** EXP-00017, the one promoted effect, failed its own
  out-of-sample re-test. Terminal report filed. Phase parked.

## What worked

1. **Governance as the immune system.** The fail-closed promotion gate
   rejected every unqualified candidate — including ones that *looked* great
   in-sample. The gate saying "no" ~40 times is the single most successful
   behavior of this project.
2. **Frozen criteria before results.** Every screen pre-registered its kill
   criteria (power, significance, absolute, cost). This prevented the classic
   failure mode: tuning until something passes.
3. **Negative results as first-class artifacts.** Every rejected hypothesis is
   documented with a reproducible script (`research/neg_results/`). The map of
   dead ends is worth more than one backtest that "works."
4. **Cost-awareness from bar one.** Spread + slippage + commission modeled
   from the first screen, not bolted on after — which is exactly why most
   candidates died honestly.
5. **Infrastructure quality.** Execution engine, event sourcing, risk limits,
   reconciliation, IBKR adapter, WF-v2 protocol — all tested, all
   instrument-agnostic, all deployable today.

## What didn't

1. **Infrastructure-before-alpha.** The fortress was built before the treasure
   was found. An immaculate pit crew with no car. Years of governance around
   an empty vault.
2. **The governance spiral.** Each evaluation surfaced a new gap → new ADR →
   new audits → new gaps. ADR-023 correctly closed a bypass but left the
   schema without the columns it needed — gates locked with no path through.
3. **Single-dataset research.** 12 months of EURUSD/GBPUSD was the only data;
   every "OOS" was in-sample or anchored within it. Honest WF was structurally
   impossible until the second window was acquired (which only happened at the
   very end).
4. **Document sprawl.** 58 root markdown files, many superseded; AGENTS.md
   pointed at files that no longer existed. Governance weight exceeded the
   amount of *behavior* being governed.

## Key numbers

- 807 tests green (strategy/research/data/backtest/replay/recovery/adapters).
- ~40 experiments across 6 structural axes, 2 asset classes, 15+ signal
  concepts.
- 0 surviving strategies at the promotion gate. 0 bad trades placed.
- 22 ADRs; 1 promoted effect — which then failed its own OOS re-test.

## Lessons (for the next phase, wherever it lives)

1. **The gate saying "no" 40 times IS the success.** An honest system that
   refuses to trade a phantom edge costs nothing and loses nothing. Most
   retail systems fail by promoting — TITAN failed safely.
2. **Negative results are the deliverable.** A documented, reproducible dead
   end is permanent edges. rediscovered.
3. **The "fortress before treasure" anti-pattern.** Any future project should
   sequence: cheap honest screen → evidence → THEN infrastructure that is
   proportional.
4. **New data before new backtests.** Never evaluate a second hypothesis on
   the window it was invented on. Sequestration is discipline.

## What survives (and is worth keeping)

- The **platform**: execution/risk/gate/screening/WF layers — instrument- and
  signal-class agnostic, tested, deployable now.
- The **methodology**: pre-registered criteria, cost-aware engine, honest OOS,
  negative-results library as the search map.
- The **discipline**: the process that said no 40 times correctly.

If a genuinely different alpha source ever appears — one that does not fit the
"OHLCV directional on liquid instruments" pattern (microstructure/OFI,
capacity-constrained niches, a fundamentally new data type) — the system is
ready to evaluate it with more integrity than any retail project. That is the
durable value of what was built.