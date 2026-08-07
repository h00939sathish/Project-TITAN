# P4 (multi-TF confluence) — FAIL (frozen kill criteria)

- **Experiment:** P4_multi_tf_confluence (debated pivot Phase 1, pivot-options.md)
- **Date:** 2026-08-08
- **Concept (frozen):** 4H close > 20-SMA momentum, entered ONLY when 30-day
  daily realized vol of the previous completed day > 50th percentile of the
  trailing ~150 daily-vol values. No same-day lookahead.
- **Data:** Dukascopy 1m->4h, 2025-08..2026-07, EURUSD (gate pair) + GBPUSD
  (OOS robustness only).
- **Result (anchored 2-fold OOS, combined):**

| Pair | ungated Sharpe | gated Sharpe | gated trades | bootstrap frac>0 |
|---|---|---|---|---|
| EURUSD | 19.25 | 14.53 | 18 | 0.000 |
| GBPUSD | 21.13 | 14.70 | 20 | 0.000 |

- **Decisions vs pre-registered kill criteria (ALL required to pass):**
  1. Power (gated OOS trades >= 60): **FAIL** (EURUSD 18).
  2. Significance (gated beats ungated at 95%, 1000x block bootstrap): **FAIL**
     — frac>0 = 0.000 on BOTH pairs; the daily-vol gate makes momentum WORSE,
     not better.
  3. Absolute (gated OOS Sharpe >= 0): PASS (14.5/12.2).
  => **P4 FAIL** (2/3 killed).

- **Honest caveats.** The annualized Sharpes (~19-21) are drift artefacts of
  flooring |return| smoothing / long-biased path in an uptrending window, NOT a
  tradeable signal. That is why the bootstrap DIFFERENCE (gated vs ungated) is
  the decisive test and it is decisively negative. These Sharpes are for
  absolute-listed baseline only; the finding that the vol gate hurts is
  robust.
- **Conclusion / ban triggered:** per Decision C, single-pair directional OHLCV
  on FX majors — now with regime gating — is permanently banned. P4 FAILS.
  The multi-TF / daily-regime-confluence axis is now closed (it does not help
  momentum on FX).
- **Trigger next:** Phase 2 (P2) — non-FX instrument pivot (gold/S&P futures),
  pending a new instrument+data decision (not auto-executed; needs another
  debated choice and, for gold, a real data pull).