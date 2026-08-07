# TITAN FX — Pivot Options (debated) & Phase-1 Decision

> Status: Draft (research decision record, informational — not an ADR).
> Source: multi-model debated plan `pivot-options.md` (nemotron/minimax →
> gemini). Evidence-led, no fabrication, no promotion.

## Context

The FX directional search on 2025-08..2026-07 EURUSD+GBPUSD is exhausted
(EXHAUSTION_MEMO.md): 15 concepts 0/15, carry EXP-23/24 rejected, cross-pair
MR non-cointegrated, vol-clustering EXP-17 fails 2-fold OOS. Untested axes:
other instruments, multi-TF confluence, microstructure/OFI, longer history.

## Ground truth (verified, corrects debate path hallucination)
- XAUUSD spot gold is instrument-wired (ADR-015, `spot_metal_instrument`)
  but has only a 7-line smoke fixture (no real history) — tradeable-ready,
  needs a data pull to be searchable.
- Broker/data hooks wired: IBKR, Alpaca, yfinance, Dukascopy.
- Prior FX window (2022-08..2025-07) downloading to
  `research/dukascopy_1m_ba_prior/` (sequestered; not to be used for P4
  design).

## Decided (debated)
- **A: Execute P4 (multi-TF confluence) first, P2 (futures: gold/S&P) as the
  immediate fallback.** P1 (cross-pair FX) and P3 (tick/OFI) rejected. P5
  (park) is terminal if P4+P2 fail.
- **B: First screen = 4H momentum gated by daily vol regime.** 4H close >
  20-SMA, executed only when 30-day daily realized vol is >50th percentile of
  trailing ~1yr. Kill criteria: (1) power ≥60 combined OOS trades; (2) gated
  beats ungated OOS Sharpe at 95% via 1000× block bootstrap; (3) gated OOS
  Sharpe ≥0. GBPUSD = OOS robustness only.
- **C: Permanent bans** — single-pair directional OHLCV on FX majors without
  regime gating; vol-clustering-as-alpha on FX majors; parameter tweaking;
  prior-window snooping; cross-protocol meta-search.
- **D: Prior window sequestered** as final global OOS, only queried if P4
  passes, validated vs WF-v2 eligibility rules.

## Phase 1 next step
Implement the P4 screen (`research/p4_multi_tf_confluence.py`) to the frozen
spec and run it against the kill criteria. On PASS → validate prior window and
run frozen model on it (global OOS). On FAIL → log ban + trigger P2.