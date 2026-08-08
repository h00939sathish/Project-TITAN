# NEGATIVE RESULT — P2: Macro-Momentum on Spot Gold (DFII10 + DBC)

- **Hypothesis:** Golden macro-momentum — long gold when real yields are
  falling (DFII10 252d) and/or broad commodities rising (DBC 252d), equal
  weight. Structurally distinct from the failed FX axis (no gold-price OHLCV
  signal).
- **Dataset (all acquired this session, official/free):** gold GC=F daily
  2000-08..2026-08 (6,508 rows); DBC 2006-02..2026-08 (5,158 rows); DFII10
  real yields 2003-01..2026-08 (5,904 rows, official US Treasury XML — FRED's
  endpoint was network-blocked).
- **Window:** frozen 2007-01..2023-12 (GFC/ZIRP/2022 coverage), anchored 2-fold
  OOS, cost 1.0 bps RT, long-only (ADR-015), vol-scaled to 10%.
- **Result (OOS, 2 folds):**

| Frozen kill criterion | threshold | result | verdict |
|---|---|---|---|
| net ann. return | >4% | 1.49% | FAIL |
| OOS Sharpe | >0.45 | 0.31 | FAIL |
| profit factor | >1.20 | 1.14 | FAIL |
| max OOS DD (at 10% vol) | <20% | 8.41% | PASS |

  Robustness window 2010..2023 also FAILS.

- **Decision:** REJECT. Macro-momentum on spot gold does NOT clear the frozen
  kill criteria (3/4 killed). The signal class (real-yield + commodity
  momentum) is now tested and rejected on this data, with the same
  discipline as every other axis.
- **Failure type:** Regime-dependence / weak consecutive OOS performance. The
  DBC + DFII10 drivers did not deliver gold outperformance net of costs in
  this window.
- **Triggered per debated plan:** P2 FAIL → advance toward the P5 (park)
  terminal condition; the wale search space — FX majors AND spot gold — has no
  transferable OHLCV/trend edge after costs.
- **Still untested:** microstructure/OFI (tick data — declined by budget),
  EM FX crosses / other instruments (new data), equity-index futures.
- **Reusable assets:** gold+DBC+DFII10 data pipeline, treasury XML fetcher,
  P2 screen (frozen, cost-aware, windowed), the aligned data sets.