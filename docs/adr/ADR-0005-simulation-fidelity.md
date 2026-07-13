# ADR-0005: Simulation and backtest fidelity

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** Quantitative Research Infrastructure
- **Decision scope:** Backtest engine, fill models, replay semantics
- **Supersedes / superseded by:** None

## Context

Backtest results must be reproducible and conservative. The same strategy, risk, and portfolio code paths used in paper/live operation must be exercised in replay. Fill model fidelity determines whether a strategy's backtest result is trustworthy.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §4: "research-to-live parity is a gate"; backtest/paper/live share canonical contracts.
- `../STRATEGY_ENGINE_COMPARISON.md`: Jesse's walk-forward and Monte Carlo are the strongest validation patterns.
- `../BACKTEST_ENGINE.md`: bar-conservative fills are the minimum default; order-book simulation is deferred.

## Decision

1. **Identity of contracts.** Replay uses the exact same `core/src/` Rust types (risk gate, order state machine, portfolio projection) as the paper/live path. The only replaced component is the broker adapter (simulated adapter for replay, live adapter for paper/live).
2. **Bar-conservative fills are the default.** Fill at next bar's open/close with configurable slippage and commission. Quote-based fills are an opt-in higher-fidelity mode when data is available.
3. **Determinism is mandatory.** Identical inputs (data partitions, strategy package digest, parameters, seed, fill model config) produce byte-for-byte identical event streams. Enforced by golden replay tests.
4. **Walk-forward and Monte Carlo are not MVP scope.** They are added after the baseline replay engine has golden coverage (Phase F gate).

## Alternatives and trade-offs

- **Order-book fill model as default** — would require L2/L3 data for every instrument and is significantly slower. Deferred; the replay throughput budget (1M events / 15s) assumes bar-conservative.
- **Tick-level replay** — highest fidelity but highest data and compute cost. Deferred.
- **Python-only replay** — would avoid Rust FFI overhead for the replay loop. Rejected; replay must use the same Rust types as live operation to guarantee parity.

## Consequences

- Bar-conservative fills are optimistic for strategies that depend on quote dynamics or queue position. This is documented in the replay result metadata.
- Replay determinism requires fixed seeds, fixed input partitions, and pinned code/environment digests.

## Validation and operations

- Golden fixture: identical inputs → identical fills, positions, PnL, metrics across runs.
- Fill model calibration: conservative fills never overstate capacity.
- Corporate actions: split-adjusted prices produce correct PnL.
- Replay throughput budget validated in Phase D.

## Approval

Architecture Council — 2026-07-13
