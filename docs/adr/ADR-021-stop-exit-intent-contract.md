# ADR-021: Express strategy exits (stop / take-profit / trailing) at the intent layer

- **Status:** Proposed (awaiting Architecture Council + Risk Owner)
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner, Execution Platform
- **Decision scope:** Strategy signal contract, `TradeIntent`, execution adapters (IBKR first)
- **Supersedes / superseded by:** None; extends ADR-014 and ADR-018 (paper FX execution)

## Context

The paper data path now carries full OHLC to strategies (PR #10, merged master
`03cf940`: the TWS realtime feed exposes `open/high/low/close/volume`, and the
bridge can forward a completed bar to a strategy). A trailing-stop strategy such
as `traderdev-ema9-vwap` (EXP-00025, PR #11, candidate — not promoted) has
valid OHLC-aware exit logic (`update_bar`), but the **execution path cannot
express it**.

Today the strategy signal contract is directional only. A strategy emits
`"BUY"` / `"SELL"` / `None` per completed bar; the bridge builds a `TradeIntent`
with a single `side`, `price`, `quantity` and no exit tooling; the
engine/adapters turn it into a bare market/limit order. There is no way to
express "enter here, stop at price X", "take profit at Y", or a ratcheting
trailing stop. Concretely:

- `TradeIntent` **already declares** an optional `stop_price`
  (`core/src/messages.rs:117`), and the engine → adapter plumbing forwards it
  (`engine.py:673`, `alpaca_adapter.py:264`).
- **Nothing ever sets it**: no strategy, bridge, or runner populates
  `stop_price`, and no strategy carries a trailing-stop instruction at all.
- The IBKR adapter ignores it — it maps `order_type` to `LMT`/`MKT`
  (`ibkr_adapter.py:254`) and never builds `STP`/`TRAIL` orders or passes a stop
  price.

The 2026-08 review of the F1 candidate surfaced this disconnect: research-harness
results (+408 pips pooled on FX 4h) could not be reproduced through the engine's
bar-close, directional-only model, because the trailing-stop **lifecycle** (arm,
ratchet, intrabar pierce) was dropped at the intent boundary.

## Evidence

- PR #10 (merged): OHLC now flows feed → paper session → bridge → strategy.
  `695` tests pass across strategy/research/data/backtest/replay.
- `TradeIntent.stop_price` exists (`messages.rs:117`) and flows to engines
  (`engine.py:673`) but is never populated by any producer.
- IBKR adapter builds only `LMT`/`MKT` (`ibkr_adapter.py:254`); no stop/trail order.
- `EXP-00025_traderdev_families.json`: F1's edge required the ATR-trail exit;
  the engine's directional model could not carry it through to a fill.
- ADR-014 / ADR-018 establish the paper-first, gate-parity execution boundary
  this work must respect.

## Decision

Adopt an **exit-bearing intent contract** so a strategy can request protective
exits at the point of order placement, expressed as **absolute price levels** on
the intent (no strategy-side assumption about broker mechanics):

1. The `TradeIntent` (and its exit-side message) carries explicit, optional,
   broker-agnostic exit levels:
   - `stop_price` — initial protective stop (loss side, absolute price)
   - `take_profit_price` — initial profit target (absolute price)
   - `trailing` — a trailing controller described by `(activation_distance,
     trail_distance)` in price terms, so the strategy declares how far the stop
     lags price rather than how a vendor menu is clicked.
2. The **strategy layer is responsible for signal + exit levels only** — it
   produces levels from its own state (e.g. ATR × multiple on bar close). The
   **engine/adapter layer is responsible for the persistence semantics** of the
   trailing stop (arm, re-issue on each completed bar, ratchet) and their
   observable broker behavior.
3. **Backtest parity gate**: this intent must be expressible in the replay model
   with intrabar high/low pierce detection, so a strategy's research result is
      reproducible through the engine (closing the EXP-00025 F1 gap).
4. **Paper-first realization**: the IBKR paper adapter is the first target to
   map these levels to `STP`/`TRAIL` (or GTC stop orders, subject to per-account
   entitlement evidence), gated exactly like ADR-018. Live path untouched.
5. **No promotion side effect**: enabling exit intents does not promote any
   strategy. `traderdev-ema9-vwap` remains a candidate until it independently
   clears the promotion gate.

## Alternatives and trade-offs

- **Keep directional-only signals; have strategies own their position/exit
  state internally.** Rejected: strategies are pure calculators per the AGENTS.md
  boundary and their exit state is currently discarded at the intent boundary.
  Baking execution into the strategy would leak broker concerns across the
  isolation boundary.
- **Use vendor-native fields only (IBKR `STP` / `TRAIL`, etc.).** Rejected:
  couples the strategy/runtime contract to one broker, violating the intent
  abstractions used elsewhere and ADR-018's isolation.
- **Do nothing; keep the close-only proxy.** High risk: keeps trailing-stop
  strategies untradeable and transfers the research→engine unreproducibility to
  every future strategy of this kind.
- **Add `stop_price` to IBKR and stop there.** Partial: does not capture the
  ratcheting trailing knob or the replay parity intent, so most protective exits
  stay inexpressible.

## Consequences

- A trailing/stop strategy can state its full exit once, and the engine carries
  it through placement, amendment, and log. The audit trail records the exit
  levels machine-readably.
- EXP-00025 F1 becomes implementable as a paper candidate whose engine result
  matches the harness once the parity gate lands.
- This is **proposal/implementation** work only: no promotion, no live
  enablement, no change to any agent's order-placement authority.

## Validation (gate criteria per the implementation gate in AGENTS.md)

1. Spec exists: update `StrategyRuntime.spec.md`, `Execution.spec.md`, and
   `TradeIntent.spec.md` for the exit-intent fields. This ADR records the
   decision.
2. Tests for each exit class: stop arm, take-profit, trailing ratcheting,
   intrabar pierce in the replay engine; IBKR mapping of exit intents to
   stop/trail orders via mocks; reconciliation of the resulting fill. Covered
   includes the F1 candidate (paper/replay only).
3. Acceptance criteria at the implementation gate (per AGENTS.md 6-condition
   gate): defined measurable parity (harness vs engine) on the EXP-00025
   families; replay + IBKR paper evidence; unit/contract/integration tests for
   every state transition (arm, running, hit, cancel); rollback documented; a
   "position on trailer without any exit intent" invariant surfaced as a runbook
   check and logged.

## Rollback

- Revert the exit-surface changes. Any paper session running these falls back to
  entry-only (no protective stops), preserving all kill-switch and reconcile
  semantics. The intent struct's existing optional fields keep the message
  serializer compatible; removing new optional fields falls back without data
  loss or partial state.
- No margin/rollover behavior changes.
- No strategy promotion is part of this record.

## Approval

Architecture Council — pending

Risk Owner — pending