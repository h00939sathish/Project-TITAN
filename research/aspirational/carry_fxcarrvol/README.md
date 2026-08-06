# Aspirational / Draft — FX-CARRY-VOL carry strategy (QUARANTINED)

**Status: NOT ACTIVATED. Do not wire into any session or live/paper strategy.**

These files were created by an external agent and declared "Activated" in a
walkthrough, but that claim is FALSE and contrary to the research gate:

- They are a hardcoded (2023-era) rate table, not an ingestion pipeline —
  `rate_differentials.py` used USD 5.25 / EUR 3.75 vs actual 2026-07 DFF 3.63 /
  ECBDFR 2.25 (a ~160bps fabricated carry differential).
- The real experiment **EXP-00024 (vol-weighted carry) was REJECTED** on
  2026-08-06 (avg net Sharpe 0.26, temporal stability 0/4) — see
  `research/neg_results/EXP-00024_vol_carry.md`. Building/starting a strategy from
  a rejected hypothesis violates the research pipeline. The canonical backlog
  (RESEARCH_BACKLOG.md) lists RQ-FX-001 as Ratified / In-Progress, not Activated.

Kept only as a design reference / draft; move here reversed no behaviour. Re-open
RQ-FX-001 only via a NEW hypothesis that survives a proper experiment.