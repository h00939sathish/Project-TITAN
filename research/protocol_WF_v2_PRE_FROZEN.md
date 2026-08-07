# WF-v2 Walk-Forward Protocol (PRE-FROZEN) — for NEW out-of-sample data only

Pre-frozen per the debated plan (Step 4) BEFORE acquiring any new data. No
parameter tuning once frozen. Any future OOS evaluation of a candidate on NEW
data must follow this protocol verbatim; deviations invalidate the result.

## 0. Mandate (from the debated plan)

The 12-month 2025-08..2026-07 EURUSD+GBPUSD window is exhausted (directional
FX 0/15, carry rejected EXP-23/24, cross-pair MR non-cointegrated, and the
promoted vol-clustering effect **failed its 2-fold OOS re-test**, IC 0.053/0.038
in fold 2). The only +EV lever is NEW, regime-diverse out-of-sample data. This
protocol is locked NOW so no post-hoc criteria can be invented later.

## 1. WDII input data eligibility (all must hold)

- [ ] New window strictly non-overlapping with 2025-08..2026-07 (e.g. prior
      2022-08..2025-07), OR pairs not in the exhaust (EUR/GBP 2025) — never
      re-use the in-sample window for OOS.
- [ ] >= 24 contiguous months of 1m bars, resampled to the tested timeframe.
- [ ] Missing-tick rate < 5%.
- [ ] Regime coverage: at least one major central-bank pivot within the window
      (Fed/ECB cut/cut or hike cycle) so out-of-regime durability is tested.

## 2. Anchor scheme (locked, no alternatives)

Expanding/anchored walk-forward:
- Train: expands from a 6-month minimum, growing monthly.
- Test: fixed 1-month window after each train, rolled monthly.
- No overlapping test months. No re-training inside a test window.

## 3. Candidate protocol (who gets tested)

- Only strategies that survived the cheap screen AND have an accepted evidence
  record (registered candidate, no promotion). No on-the-fly parameter fits.
- A candidate may be a *directional* signal, the vol-regime *sizing* overlay,
  or a new microstructural/structural feature — but in ALL cases the WF uses
  this same protocol.

## 4. Pre-registered pass criteria (locked)

- OOS Sharpe > 0.0 AND information coefficient (IC) of the signal vs forward return
  > 0.02 in >= 70% of test windows, averaged positive.
- Turnover: annualized one-way turnover <= 60x to be trade-safe after costs.
- Cost model: the SAME cost-aware engine (spread + slippage_bps +
  commission_bps) used throughout the ORIGINAL screens — a candidate must be
  net-positive after these exact costs in OOS.
- Margin: none of the above may be relaxed post-hoc.

## 5. What is strictly banned

- Tuning any parameter inside / after observing the OOS window.
- Re-selecting parameters because OOS underperforms.
- Using the 2025-08..2026-07 in-sample window as part of OOS.
- Generating synthetic data to "fill time" if acquisition fails.

## 6. Data acquisition (Step 5) — order of preference

1. Dukascopy 1m bars for a PRIOR multi-year window (2022-08..2025-07) — free,
   time to scrape.
2. Add USDJPY / USDCHF (pairs not in the existing set) for cross-section.
3. Paid tick data (6+ months) for OFI/microstructure ONLY if budget allows;
   OFI cannot be expressed in the current OHLCV pipeline and is the one
   structural class the current data cannot test.

## 7. Terminal decision gate

- PASS: propose paper-trading pilot with strict risk limits (still no live).
- FAIL: no promotion; either pivot to a new structural/data class or write the
  exhaustion memo. Do not loop on the same strategy+data.

---
Status: PRE-FROZEN. Only changeable by a human decision recorded in an ADR.