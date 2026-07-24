# Experiment: ma-crossover on 5m

**Date:** 2026-07-24
**Strategy:** ma-crossover
**Timeframe:** FIVE_MINUTES
**Parameters:** {"fast": 5, "slow": 20}

## Status

PENDING — evidence not yet collected. Daily-only evidence exists.
Intraday qualification requires separate walk-forward, Monte Carlo,
fee/slippage, data-quality, and paper-session evidence per ADR-017.

## Required Evidence

- [ ] Walk-forward (OOS period, parameter stability)
- [ ] Monte Carlo (shuffle, bootstrap, OOS)
- [ ] Fee/slippage model (spread, commission, market impact)
- [ ] Data-quality check (survivorship, delisting, corporate actions)
- [ ] Paper-session validation (TITAN paper runtime, min certified notional)

## Source

Daily registration in `registrations.py` — daily only.
