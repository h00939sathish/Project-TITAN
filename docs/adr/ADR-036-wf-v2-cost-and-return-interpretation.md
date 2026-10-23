# ADR-036: WF-v2 cost and return interpretation

- **Status:** Accepted (2026-10-24) — approved by the project owner
- **Date:** 2026-10-24
- **Owners:** Project owner (sole decision-maker for TITAN research protocol)
- **Supersedes:** N/A (interprets, does not edit, `research/protocol_WF_v2_PRE_FROZEN.md` §4)

## Context

`titan research run` (`src/titan/research/wf_v2.py`) runs the frozen WF-v2
protocol. Section 4 of that protocol says:

> Cost model: the SAME cost-aware engine (spread + slippage_bps +
> commission_bps) used throughout the ORIGINAL screens — a candidate must be
> net-positive after these exact costs in OOS.

> Turnover: annualized one-way turnover <= 60x to be trade-safe after costs.

The "original screens" engine is `backtest()` in `research/traderdev_fx_screen.py`.
On review (commit 052ae15) it had two defects:

1. **Short sign.** A short position earned the *positive* bar return, so a short in
   a rising market made money.
2. **Flip cost.** Every position change was charged `COST_RT/2` regardless of size
   or leverage. A long -> short flip (two units) paid half a round trip, and the
   charge ignored the 1.25x vol-target leverage that the returns used.

Copying that engine literally would carry both defects into every WF-v2 verdict.
The protocol is frozen and is not edited; this ADR records how its wording is
applied.

## Decision

WF-v2 uses the original screen's cost *level* and charging structure, with the two
defects corrected:

- **Cost level:** `COST_RT = 0.8e-4` of price per round trip, all-in. This is the
  original screen's single number. It stands for spread + slippage + commission
  together; there is no separate spread term, because the original screen had
  none. Prices are bid OHLC resampled from 1-minute bars.
- **Charging basis:** `COST_RT/2` per unit of *leveraged* notional traded, on each
  bar where the position changes. Entering or exiting (0 <-> ±1) trades one unit;
  a flip (±1 -> ∓1) trades two units and so pays a full round trip.
- **Change bars earn nothing:** the bar on which the position changes pays the
  cost and earns no return (no same-bar lookahead), as in the original screen.
- **Returns:** a held position earns `position × bar return × leverage`, so shorts
  earn the negative of the bar return.
- **Sizing:** leverage = 10% vol target / 8% assumed vol = 1.25x, unchanged.
- **Turnover:** sum of |position change| × leverage over OOS bars, annualized,
  read as one-way traded notional / NAV, against the protocol's `<= 60x`.
- **Net-positive:** satisfied through the protocol's Sharpe > 0 criteria, which are
  computed on these net-of-cost returns.

### Why this is not a post-hoc relaxation (protocol §4 "Margin")

- The cost level is unchanged. The corrected charging basis charges *more* than
  the original for any strategy that flips or runs leveraged, so on costs the
  gate only gets stricter.
- The short-sign fix is direction-neutral. It corrects arithmetic the protocol
  cannot have intended, and it can move a strategy's result either way. On the
  EXP-00027 rerun it made most cells worse and one better, and changed no
  verdict (0/16 before and after; see the erratum in
  `research/neg_results/EXP-00027_traderdev_fx_evidence_screen.md`).

## Consequences

- Every WF-v2 evidence bundle embeds these rules under `interpretation`, citing
  this ADR, so a bundle states the cost model it was judged under.
- Results from the original screen engine are not comparable cell-for-cell with
  WF-v2 results. Sealed negative results stay sealed; corrections are recorded as
  errata, never as rewrites.
- Changing the cost level or charging basis needs a new ADR. It must also not be
  done between a candidate's registration and its WF-v2 run.
- **Not ratified here:** the other `INTERPRETATION` entries in `wf_v2.py` (fold
  construction, window and aggregate pass rules, missing-tick calendar, regime
  pivot, multi-instrument and verdict rules). They remain implementation choices
  pending their own review.
