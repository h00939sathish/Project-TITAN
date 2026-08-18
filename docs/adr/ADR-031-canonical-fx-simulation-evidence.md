# ADR-031: Admit FX promotion evidence only from the canonical cost-aware simulator

- **Status:** Accepted
- **Date:** 2026-08-16
- **Owners:** Quantitative Research Infrastructure, Research Owner, Risk Owner
- **Decision scope:** FX research simulation, cost configuration, walk-forward evidence, and promotion inputs
- **Supersedes / superseded by:** supplements ADR-0005 and ADR-028; supersedes no record

## Context

The current FX backtest entry points do not consistently propagate their stated cost parameters. Some call the current `StrategyRunner` with the removed `buy_qty` keyword; `run_backtest_result` supplies cost values positionally, which maps them to lot constraints rather than to slippage and commission. The generic bar model executes at a signal bar's close, uses an unversioned constant-bps commission, and does not represent the IBKR per-order minimum. Separate scripts implement different timing, bid/ask, fee, and exit semantics. Consequently, historical metrics are not mutually comparable and cannot be promotion evidence.

## Evidence

- `src/titan/research/harness.py`: positional construction maps `slippage_bps` to `step_size` and `commission_bps` to `minimum_quantity`.
- `scripts/backtest_per_timeframe.py` and `scripts/optimize_fx.py`: obsolete `buy_qty` calls fail at runtime.
- `src/titan/backtest/fills.py`: bar-close constant-bps fill model has no fee schedule, per-order minimum, quote side, or configuration digest.
- `research/run_traderdev_families.py`: separate bid/ask implementation charges commission only on exit.
- `research/ALPHA_SEARCH_TERMINAL_REPORT.md` and ADR-028: no current strategy has promotable evidence; promotion evidence must be emitted by the canonical cost-aware simulator.

## Decision

1. All new FX evidence uses one immutable `FxCostModel` and one canonical research simulator. Configuration is passed by keyword and hashed into every artifact.
2. The v1 model supports only USD-account, USD-quoted FX instruments. It uses `Decimal`, applies a fee to every fill, and calculates each commission as `max(notional_usd * rate_bps / 10_000, minimum_usd)`. Unsupported currency conversion or missing required price/quote data rejects the run.
3. Signal evaluation on bar *t* produces a pending order. A bar-only run fills it no earlier than bar *t+1* open; a quote run fills buy at ask and sell at bid. A bar-only model must carry an explicit adverse half-spread assumption and is labelled lower fidelity.
4. Walk-forward, in-sample, OOS, parameter sweeps, and promotion consume the same supplied `FxCostModel`; no routine may silently select a default model. Existing ad-hoc runs are retained as historical evidence but marked non-canonical and cannot qualify a strategy.
5. The promotion gate consumes persisted canonical evidence artifacts only. It must reject an artifact without matching data, parameter, sizing, and cost-model digests, or an artifact labelled lower fidelity.
6. This decision authorizes research simulation only. It neither authorizes broker interaction nor alters ADR-028's default-deny execution policy.

## Alternatives and trade-offs

- **Repair each script independently:** rejected; it recreates diverging semantics.
- **Use current generic bps defaults:** rejected; they silently differ by caller and cannot model ticket minima.
- **Require tick/order-book data for all work:** rejected for v1 because it prevents conservative bar research; such artifacts remain lower fidelity and non-promotable.

## Consequences

Existing return figures may change and must not be compared directly with canonical reruns. The initial scope is intentionally limited to USD-quoted FX; other instruments require their own conversion and fee schedule. The canonical simulator increases engineering work but removes ambiguity around costs and timing.

## Validation and operations

Required tests prove: keyword propagation; no same-bar fill; bid/ask side selection; both-leg fee assessment; USD minimum-fee behavior; invalid model/data rejection; sizer integer-step parity; walk-forward cost propagation; deterministic artifact digest; and promotion rejection of legacy/lower-fidelity evidence. Record `cost_model_digest`, `fill_model`, total fees, spread, slippage, rejected orders, and data/parameter/sizing digests in each artifact. Rollback disables all qualification/promotion from the simulator and preserves legacy results; it never restores old evidence as qualification authority.

## Approval

Architecture Council and Risk Owner — 2026-08-16
