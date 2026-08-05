# ADR-018: Gate IBKR paper forex execution behind a dedicated broker boundary

- **Status:** Proposed
- **Date:** 2026-07-29
- **Owners:** Architecture Council, Risk Owner, Execution Platform
- **Decision scope:** IBKR TWS/Gateway paper-only forex contract routing and reconciliation
- **Supersedes / superseded by:** Extends ADR-014; does not supersede it

## Context

ADR-014 accepts four USD-quote pairs for simulation and backtesting only. TITAN's current IBKR adapter nevertheless treats every identifier as a USD stock on SMART, which makes an FX identifier invalid for IBKR. The TWS paper-session runner also lacks FX contracts and cannot treat a strategy proposal as evidence that FX routing is ready.

IBKR's official API contract guidance defines an FX pair as `CASH` on `IDEALPRO`, with the base currency in `symbol` and quote currency in `currency`. IBKR paper accounts simulate execution against real market conditions but paper behavior can differ from live. Account permissions and market-data entitlements remain account/jurisdiction dependent.

## Evidence

- ADR-014 permits EUR/USD, GBP/USD, AUD/USD, and NZD/USD only for simulation/backtest and requires 1,000-unit micro-lot sizing.
- `src/titan/execution/ibkr_adapter.py` currently constructs every contract as `STK`/`SMART`/`USD`.
- `scripts/ibkr_paper_session.py` has only the `SPY.ARCA` ingress contract.
- [IBKR API contracts](https://ibkrcampus.com/campus/ibkr-api-page/contracts/) specifies `CASH` and `IDEALPRO` for FX contracts.
- [IBKR paper-trading limitations](https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/limitations/paper-trading) confirms paper execution is simulated and may differ from live.

## Decision

Do not implement or enable IBKR forex routing until this ADR and `specifications/Forex.spec.md` are accepted by the Architecture Council and Risk Owner. Until then:

1. Forex remains simulated/backtest-only under ADR-014.
2. `IBKRPaperAdapter` accepts only paper TWS/Gateway ports.
3. No session configuration may add an FX instrument to the IBKR execution route.
4. A future implementation must use `CASH`/`IDEALPRO`, validate micro-lot quantities, resolve a ConId, map snapshots back to canonical TITAN IDs, verify permission/data/contract availability, and fail closed on every missing snapshot or mapping.

## Alternatives and trade-offs

- **Treat FX as a stock on SMART.** Rejected: IBKR documents a different contract type and exchange; reconciliation would not be reliable.
- **Enable paper FX immediately.** Rejected: no accepted specification, no canonical snapshot mapping, and no evidence of account entitlement or reconciliation.
- **Enable live FX first.** Rejected: violates ADR-014, the paper-first execution gate, and TITAN's authority limits.

## Consequences

- FX strategy research and deterministic simulation can continue.
- The current TWS session remains equity-only until the proposal is accepted and implemented.
- A future accepted implementation needs a release gate with paper-session evidence and cannot reuse this proposed record as approval.

## Validation and operations

- Acceptance requires the test and monitoring evidence defined in `Forex.spec.md`, an approved paper-session run, explicit permission/data checks, and documented rollback.
- Rollback disables the FX session symbols, preserves audit evidence, and keeps the kill switch engaged.
- This ADR is retired only by an accepted successor that explicitly authorizes or rejects the implementation.

## Approval

Architecture Council — pending

Risk Owner — pending

