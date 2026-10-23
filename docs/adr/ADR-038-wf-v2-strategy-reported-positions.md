# ADR-038: WF-v2 reads strategy-reported positions

- **Status:** Accepted (2026-10-24) — approved by the project owner
- **Date:** 2026-10-24
- **Owners:** Project owner (sole decision-maker for TITAN research protocol)
- **Supersedes:** N/A (interprets, does not edit, `research/protocol_WF_v2_PRE_FROZEN.md` §3–4)

## Context

WF-v2 scores a candidate on the position it holds after each bar close: the
returns, costs, turnover and IC in protocol §4 are all functions of that
position. `wf_v2.positions()` derived it statelessly from the strategy's
signals: `BUY` -> long, `SELL` -> short (`long_short`) or flat (`long_flat`).

That reading is only right for stop-and-reverse strategies (`dual-ma`,
`ma-crossover`, `time-series-momentum`). `traderdev-ema9-vwap`, the one
registered candidate (EXP-00025, `research/results/ema9vwap_promotion_report.md`),
also emits `SELL` to exit a long on its trailing stop and `BUY` to exit a short.
On EURUSD 4h, 2025-08..2026-07, the stateless reading disagreed with the
strategy's own position on 786 of 1610 bars (49%) in `long_short` and 490 (30%)
in `long_flat`. The strategy is flat on 58% of bars; WF-v2 had it flat on 9%.
WF-v2 would have judged a different, almost-always-invested strategy, and a FAIL
would have sealed the real candidate as a negative result.

Protocol §3 says a candidate may be a directional signal and that WF-v2 tests
*the candidate*. Testing a different position path is not testing the candidate.

## Decision

- A strategy may report its own held position through `signal_fn.position()`,
  returning -1, 0 or +1 after each bar. When it does, WF-v2 uses that value
  directly; any other value aborts the run (`ValueError`).
- A strategy that does not report a position keeps the stateless reading above,
  so every existing result and test is unchanged.
- `long_flat` floors a reported short at flat. The strategy still runs its own
  short logic internally; WF-v2 simply does not hold the short.
- Stops act at bar-close granularity: a trailing stop that triggers inside a bar
  is held through that bar's close and exited on the next bar, which pays the
  exit cost and earns nothing (ADR-036). No intrabar fill price is modelled.
- `traderdev-ema9-vwap` reports its position (`TraderDevEMA9VWAP.position`,
  exposed by `make_traderdev_ema9vwap_signal_fn`).
- The rule is recorded as `INTERPRETATION["positions"]` and embedded in every
  evidence bundle.

### Why this is not a post-hoc relaxation (protocol §4 "Margin")

No pass criterion, cost or threshold changes. The change only makes the scored
position path equal the candidate's actual position path, and it lands before any
WF-v2 run of an affected strategy. It can move a result either way: fewer
invested bars earn less drift and also pay less cost.

## Consequences

- Strategies that use `BUY`/`SELL` as exits (`rsi`, `bollinger`,
  `vwap-reversion`, `orb`, `mean-reversion`) do not report a position yet. They
  are only correctly modelled in `long_flat`, where `SELL` -> flat is their real
  exit. A `long_short` spec for one of them is wrong until it reports its
  position; a spec author must not queue one.
- Bar-close stops differ from the cost-aware harness used in EXP-00025, which
  checked stops intrabar. WF-v2 results for trailing-stop strategies are
  therefore not comparable pip-for-pip with EXP-00025.
- Changing this reading needs a new ADR, and must not happen between a
  candidate's registration and its WF-v2 run.
