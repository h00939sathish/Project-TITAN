# EXP-00024 — COT leveraged-money positioning → forward FX returns (2013-2026)

Dataset: CFTC fut_fin_txt history zips (2010-2026) -> 8 FX contracts
(EUR/GBP/JPY/CHF/CAD/AUD/NZD/MXN), weekly net Lev_Money (leveraged money)
positioning, 4,664 ccy-week observations. Forward 20-day currency return vs USD.

## Results

- IC (positioning percentile vs forward return): **-0.025** (contrarian tilt)
- Aggregate top-bottom spread: **-0.29%/mo (t=-3.57)** — extreme net-long
  currencies underperform extreme net-short by 0.29%/mo. A contrarian trade
  (short extremes-long / long extremes-short) nets +0.19%/mo (+2.3%/yr) at
  10bps costs.
- **BUT sign-inconsistent per currency:**
  - Contrarian (negative spread): GBP -1.29, CAD -0.75, NZD -0.85, AUD -0.60,
    MXN -0.49, JPY -0.25
  - Momentum (positive spread): CHF +0.56, EUR +0.14

## Verdict

REFINE. The aggregate significance (t=-3.57) is driven by a subset of
currencies (GBP/CAD/NZD strongly contrarian; CHF/EUR momentum). Cross-instrument
sign consistency FAILS — the validator's consistency gate would not promote
this. Positioning has real predictive content but is currency-specific and
regime-dependent. Use as a FEATURE (per-currency, combined with vol/trend) or a
per-currency filter — not a standalone cross-sectional strategy.

## Reusable assets

- research/cot/fx_cot.json (8 contracts, 2013-2026 weekly)
- research/build_cot.py — CFTC fut_fin_txt parser (Lev_Money columns, exact
  contract-name matching to avoid EURO FX/XRATE false matches)
- FRED H.10 FX dataset now covers 9+ pairs 1971/1999-2026 (research/tws_daily)
