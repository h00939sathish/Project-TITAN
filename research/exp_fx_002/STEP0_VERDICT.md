# EXP-FX-002 — Step 0 Data Audit Verdict

Date: 2026-08-12
Pre-registration: C:\Users\h0093\hermes-plans\price-action-plan.md (debated + ratified R1-R11, 2026-08-12)
Audit script: research/exp_fx_002/step0_audit.py
Machine-readable result: research/exp_fx_002/step0_result.json

## VERDICT: DATA-UNAVAILABLE (per ratified R6)

Fewer than 4 qualifying pairs exist on the archive -> no promotion analysis.
The experiment is shelved, labelled, and NOT failed. This is the pre-registered
outcome of the Step 0 gate, exactly as designed.

## Per-pair audit (contract window 2021-08-01 .. 2025-07-31 UTC)

| pair   | status        | bars in window | contiguous months | missing tick % | dups |
|--------|---------------|----------------|-------------------|----------------|------|
| eurusd | FAILS_CONTRACT| 647,352        | 19                | 56.94%         | 0    |
| gbpusd | FAILS_CONTRACT| 6,203          | 3                 | 99.59%         | 0    |
| usdjpy | MISSING       | 0              | 0                 | 100%           | 0    |
| usdchf | MISSING       | 0              | 0                 | 100%           | 0    |
| usdcad | MISSING       | 0              | 0                 | 100%           | 0    |
| audusd | OUT_OF_WINDOW | 0              | 0                 | 100%           | 0    |

Contract: >= 24 contiguous months AND missing-tick < 5%, window strictly prior
to TITAN's in-sample (2025-08..2026-07). No duplicate-timestamp damage found
(dedup check clean on both files that exist).

## Root cause (evidence, not speculation)

The Dukascopy prior pull feed flapped through the entire pull window:
- EURUSD: 38 months touched but only 12 genuinely full months (>20k bars);
  four multi-month gaps (2021-10->2022-06, 2023-12->2024-02, 2024-07->2024-09,
  2024-10->2024-12). 647,352 bars but 56.94% missing vs Mon-Fri expectation.
- GBPUSD: 6,203 bars — an Aug-Oct 2021 stub.
- USDJPY/USDCHF/USDCAD: never pulled.
- AUDUSD: only post-2025-08 data (in-sample window; excluded by contract).
- Watchdog cron b13400e6a381 (dukascopy_prior_retry.py, hourly 00-06 IST)
  remains ACTIVE and grinding; last log shows UNREACHABLE days and checkpoints
  (e.g. +7,309 bars on 2026-08-11). Feed-health ceiling documented: at ~95%
  UNREACHABLE, no concurrency fix helps; time-of-day (already exploited) or a
  different route are the only levers.

## Consequences (pre-registered, no deviation)

1. No ladder compute may run on this archive (no synthetic fill, no silent
   universe downgrade — R6, R2, R10).
2. The watchdog continues automatically; Step 0 can be re-run when the pull
   completes. Re-run command: python research/exp_fx_002/step0_audit.py
3. Two forward paths BOTH require a user ruling + (for contract changes) a
   fresh pre-registration amendment debate, per the mandatory debate gate:
   a) HistData 1m fallback (bid-only, EST, documented downgrade — does NOT
      satisfy the bid/ask UTC contract; needs amendment + fixed-spread note).
   b) philipperemy/FX-1-Minute-Data GitHub/Drive mirror (same contract caveat).
4. No git commit was made; audit files are working-tree additions alongside the
   pre-existing uncommitted ADR-028 migration (untouched).

## Honesty notes

- The Step 0 gate worked: it blocked compute on data that cannot answer the
  pre-registered question. A data-logistics gap, recorded as such, is NOT an
  alpha verdict and is never dressed as one.
- The EXP-FX-002 pre-registration itself (price-action-plan.md) is complete,
  debated, ratified, and reusable the moment qualifying data exists. Nothing
  about the experiment design is invalidated by this verdict.
