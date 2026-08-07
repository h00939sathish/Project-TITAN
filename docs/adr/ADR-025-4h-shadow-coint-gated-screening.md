# ADR-025: 4h shadow-trade evidence via 1h aggregation + cointegration-gated screening

- **Status:** Accepted (2026-08-07) — lands in this PR
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner, Research Platform
- **Supersedes:** none; extends ADR-021/022/023 (gate-only promotion) and the
  debated 3-track + search-broadening plans
- **Decision scope:** shadow_events accrual for 4h candidates; searching
  non-directional FX edges

## Context

Two gaps blocked honest progress toward first shadow evidence:

1. **No shadow-events path for 4h candidates.** The FX paper session
   (`scripts/ibkr_paper_session.py`) feeds only 5m/15m/1h/1d and had no
   `shadow_events` logging. The promotion gates `shadow_sufficiency` and
   `shadow_performance` (`promotion.py`) require `simulated_side != NULL`
   rows in `shadow_events` — structurally unreachable for a 4h-native strategy,
   and running a 4h strategy on finer bars would fabricate whip evidence.
2. **Directional FX search exhausted, non-directional untested.** 0/15
   single-pair directional concepts survived the kill criterion (screening
   repo PR); carry already retired (EXP-00023/24). Cross-pair mean-reversion
   was the strongest untested, structurally-different candidate.

## Decision

1. **1h→4h BarAggregator** (`src/titan/strategies/bar_aggregator.py`): pure,
   deterministic, UTC 00/04/08/12/16/20 aligned; aggregates 1h bars into 4h
   using the research harness's exact math. Wired into the FX paper session's
   `on_bar` for candidates in `SHADOW_4H_CANDIDATES`; only 1h bars feed it; a
   completed 4h bar is forwarded to `ShadowRunner.on_price`, which simulates
   fills and logs to `shadow_events`. The qualified runtime and all non-1h
   timeframes are untouched.
2. **Search protocol (debated, EXP-00026):** screen the real EURGBP cross (1×
   cost), not a 2-leg synthetic spread; **Engle-Granger cointegration
   pre-gate** (halts if not cointegrated); 2-fold anchored walk-forward;
   contiguous-surface parameter selection; calm-vol gate rejected per
   evidence.

## Result

The cointegration gate **halted EXP-00026** — the EURUSD/GBPUSD spread is not
cointegrated over the full window (Engle-Granger p=0.54; ADF non-stationary),
so cross-pair MR is not screened. Earlier solo screening claiming a spurious
~+535 pips/yr edge on a non-stationary series was corrected by the gate.

## Consequences

Positive: a real shadow-events path exists for any 4h candidate; the
cointegration gate prevents trading a non-stationary spread; screening is
evidence-led. Negative: cross-pair MR on this pair is REJECTED; the shadow
clock hasn't accrued a qualifying trade yet for any strategy.

## Verification

- `tests/strategies/test_bar_aggregator.py` (7 tests: OHLC/volume math,
  boundary alignment, flush/isolation/naig).
- `tests/shadow/test_shadow_events_path.py` (2 tests: aggregator→runner→
  shadow_events round-trip; gate predicate counts).
- `tests/screening/test_screen.py` (3 tests: cost model, kill gate).
- 21 tests green across shadow/screening/aggregator/schema/promotion.

## Rollback

Remove the aggregator wiring + `SHADOW_4H_CANDIDATES` from the session and
drop the BarAggregator module; the session returns to 1h-only. Remove the
screening script and result; no state in chronicle is written by the screen.