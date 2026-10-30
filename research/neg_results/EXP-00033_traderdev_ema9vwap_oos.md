# NEGATIVE RESULT — EXP-00033: traderdev-ema9-vwap on unseen years (WF-v2)

- **Hypothesis:** the registered F1 candidate (EMA9 vs a 120-bar VWAP, ATR-14
  trailing stop at 2.0x) keeps a positive, cost-surviving edge on the three
  years it was never tuned on. EXP-00025 measured +408.3 pips pooled on
  EURUSD + GBPUSD, but over the 12 months the port was tuned on.
- **OOS run:** frozen parameters, 2022-08..2025-07, 240m bars, bid-only resample,
  30 test months each, protocol `WF_v2_PRE_FROZEN` (sha256 a524427b2e8b).
- **Result: FAIL on both instruments.**
  - EURUSD: 7/30 windows passed; mean Sharpe +0.038; mean IC **-0.005**;
    turnover **97.9**/yr vs 60 cap; net OOS +3.06%.
  - GBPUSD: 4/30 windows passed; mean Sharpe **-1.04**; mean IC **-0.033**;
    turnover **91.8**/yr vs 60 cap; net OOS -5.54%.
- **Decision:** REJECT. No promotion. The +408 pips does not reappear on unseen
  years, and the two criteria that fail everywhere are the ones that are not
  parameter-shaped: the information coefficient is negative (the signal points
  the wrong way more often than not) and turnover is ~1.6x the cap on both
  pairs, so costs alone would erase a positive gross edge.
- **Failure type:** in-sample tuning on a surface with no compact plateau.
  EXP-00025 already reported that the 2D parameter surface had no plateau and
  that the two pairs favoured different corners; this run confirms that finding
  rather than adding a new one.
- **Caveats recorded, and why neither changes the verdict:**
  - VWAP is volume-weighted, and the prior window's weights are the vendor's
    bid candle volume while the tuning window's were tick counts. Different
    activity measures, so cross-window VWAP levels are not strictly
    comparable. It cannot make a -1.04 Sharpe and 1.6x turnover cap into a pass.
  - The vendor returns only 1 bar/day for EURUSD on 2024-12-02..06 (5 of 782
    sessions). Too small to move any criterion by an order of magnitude.
- **Data:** `research/dukascopy_1m_ba_prior/` (EURUSD sha256 48f719fc2dda,
  GBPUSD 396a611bad6c), built 2026-10-27 from the Dukascopy widget candle API;
  audited clean (no Saturday bars, 0.005% zero-volume, 0 OHLC mismatch against
  the bi5 route on 190,188 shared minutes). Provenance in
  `logs/dukascopy_jetta_20261027.job.json`.
- **Reusable assets:** the prior dataset itself (the first honest OOS window
  TITAN has had), `scripts/pull_dukascopy_jetta.py`, `scripts/validate_prior_candles.py`,
  and the WF-v2 harness with a second instrument pair exercised end to end.
- **Consistency:** joins EXP-00016/19/20/21/22/26 — directional FX alpha does
  not survive honest out-of-sample evaluation on Dukascopy data. The only
  difference here is that this one was TITAN's last registered candidate, so
  the F1 family is now closed rather than merely unconfirmed.
