# ADR-026: EXP-00017 fails 2-fold OOS re-test — freeze data exhaustion

- **Status:** Accepted (2026-08-07) — a research-branch decision record
- **Date:** 2026-08-07
- **Owners:** Architecture Council, Risk Owner, Research Platform
- **Supersedes:** the promotion assumption behind EXP-00017 (see below)
- **Decision scope:** whether the vol-clustering effect (the system's ONLY
  promoted effect) survives out-of-sample, and how to proceed

## Context

The multi-model debated plan (next-search-leverage.md) set a **gating Step 1**:
re-test EXP-00017 (vol-clustering) with a pre-registered 2-fold anchored OOS
criterion (Spearman IC ≥ 0.10 both folds, same sign, none < 0.05) before any
downstream work.

## Result (executed 2026-08-07, research/exp17_2fold_retest.py)

| Pair | OOS fold 1 | OOS fold 2 | Verdict |
|---|---|---|---|
| EURUSD | 0.121 | 0.053 | FAIL |
| GBPUSD | 0.098 | 0.038 | FAIL |

The only promoted effect does NOT clear the OOS bar. The original EXP-00017
"temporal" thirds (IC 0.22–0.33) were same-window sub-periods, not
out-of-sample — so it was promoted without true OOS validation.

## Decision

- Close the "test on this dataset" branch. Do not run further parameter/strategy
  mining on the 2025-08..2026-07 EURUSD/GBPUSD window.
- Freeze the WF-v2 protocol (`research/protocol_WF_v2_PRE_FROZEN.md`) before
  acquiring any new data.
- The only positive-expected-value lever is NEW regime-diverse OOS data (prior
  multi-year window and/or pairs not in the current set); tick data for
  microstructure/OFI is the structural direction the current OHLCV cannot test.
- No promotion; paper/research boundary retained.

## Consequences

Honest: the system currently has NO OOS-validated tradable edge on this data.
Negative: the vol-clustering "promoted" designation is now qualified. Positive:
the plan's FAIL branch prevents wasted compute and keeps the path forward
evidence-led.

## Verification

`research/exp17_2fold_retest.py` + `research/results/EXP-00017_2fold_retest.json`.
Reproduces EXP-17 FX-002 construction on Dukascopy 1m→1h.

## Rollback

Restore any future use of the 12-month window for insertion-quality OOS by
human decision; the pre-frozen protocol governs all future OOS evaluation.