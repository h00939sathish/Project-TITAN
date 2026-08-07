# TITAN FX — Exhaustion Memo (scoped)

> Scope: this memo covers the **FX single-pair directional search on the
> 2025-08..2026-07 Dukascopy window**. It draws the line between what is
> honestly exhausted and what is untested. It does not decide the project's
> future — it documents the evidence for that decision.
> Date: 2026-08-07. Status: informational (not an ADR).

## 1. What is exhausted (tested, evidence on file)

**Single-pair directional OHLCV on EURUSD/GBPUSD, 4h, after costs.**

| Search | Result | Evidence |
|---|---|---|
| 15 academically-backed directional concepts (momentum, mean-reversion, breakout, MACD, RSI, PSAR, VWAP-reversion, ORB, stoch, etc.) | **0/15 survive** ≥200 pips/yr net × 2 pairs | `scripts/screening/results.json`, `screen.py` |
| Vol-regime gating on the best candidate | Does NOT rescue (reduces edge) | screening run, EXP-26 |
| EMA9×VWAP candidate (F1 family) | NOT QUALIFIED 4/7 gates; surface fragile, pair-specific | `ema9vwap_promotion_report.md` |
| Carry / rate differential | REJECTED (EXP-00023, EXP-00024): only mechanical accrual, no UIP spot anomaly | `neg_results/EXP-00023/24` |
| Cross-pair mean-reversion (EURUSD vs GBPUSD) | **HALTED at Engle-Granger cointegration gate** (p=0.54 full window; non-stationary) | `EXP-00026_crosspair_mr.md` |
| Vol-clustering (EXP-00017, the only promoted effect) | **FAILS 2-fold OOS re-test** (EUR 0.121/0.053, GBP 0.098/0.038) | `EXP-00017_2fold_retest.json`, ADR-026 |

**Verdict on this branch:** directional FX on majors with single-timeframe
technical indicators is exhausted on this data. Search space closed. (A
dataset-wide note: the whole 12-month window is tuning-seen; it cannot serve
as OOS for anything tuned on it.)

## 2. What is NOT exhausted (untested, structurally different)

These are *different alpha sources*, not variations of the above. Any of them
is a candidate for the future search — none is a claim that they work:

1. **Different instruments.** FX majors are the most efficient market on
   earth. Commodity/index futures, EM FX crosses, or rates were never tested.
   Requires new data (new acquisition in progress — prior window 2022-08..
   2025-07 pulling to `research/dukascopy_1m_ba_prior/`).
2. **Multi-timeframe confluence.** A 4h signal filtered by a daily regime was
   never screened (all 15 concepts ran single-TF).
3. **Microstructure / order-flow (OFI).** Cannot be expressed in OHLCV;
   requires tick data. Decided: **no tick spend** until a microstructure
   concept survives cheap OHLCV screening first.
4. **Same instruments, longer/historical window.** The prior window (now
   downloading) enables honest WF-v2 under the pre-frozen protocol — but only
   for NEW hypotheses, never to resurrect the dead 15.

## 3. The line

**Searched thoroughly, nothing found:** single-pair directional, single-TF,
OHLCV, FX majors, one 12-month window, after realistic costs. ~30 experiments,
15 concepts, 1 marginal candidate, 0 survivors, promoted effect fails OOS.

**Untested, different structure:** other instruments, multi-TF confluence,
microstructure/OFI, longer regime-diverse history.

## 4. What this memo is for

- The honest foundation for the next decision: continue FX research in a
  different direction, or redirect the project to other instruments/asset
  classes.
- A guard against repeating the dead search (the "resurrect the 15 on a new
  window" failure mode).
- Not a promotion request, not a farewell: a boundary document.

## 5. Open state

- Prior-window download: running (EURUSD, GBPUSD, 2022-08-01..2025-07-31).
- WF-v2 protocol: pre-frozen (`protocol_WF_v2_PRE_FROZEN.md`).
- No strategy is qualified; nothing is promoted; no live capital.