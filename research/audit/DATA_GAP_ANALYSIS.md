# DATA GAP ANALYSIS

**Date:** 2026-09-29. *Can TITAN answer the questions its own strategies require?* **No.**

## 1. What is actually on disk

| Path | Status | Size | Files | Covers |
|---|---|---|---|---|
| `research/fx_clean_5m` | **EXISTS** | 21 MB | 3 | EURUSD, GBPUSD + 1, 5m |
| `research/fx_clean_daily` | **EXISTS** | 92 KB | 3 | G10 daily |
| `research/fred` | **EXISTS** | 3.3 MB | 29 | Macro (DFII10, DBC, rates) |
| `research/gold_assets` | **EXISTS** | 1.4 MB | 2 | XAUUSD |
| `research/intraday_backtests` | **EXISTS** | 1.6 MB | 21 | **2026-07-29/30 only — 2 days** |
| **`research/dukascopy_1m_ba`** | **ABSENT** | — | — | **gitignored `.gitignore:101`** |
| **`research/crypto/data`** | **ABSENT** | — | — | **gitignored `.gitignore:143`** |
| **`research/equities/data`** | **ABSENT** | — | — | not present |

## 2. The reproducibility failure — the most serious data finding

`research/dukascopy_1m_ba/` is referenced by **seven** production scripts:
`traderdev_fx_screen.py:37` · `run_traderdev_families.py:20` · `screen.py`→`m.DATA` ·
`exp17_2fold_retest.py:20` · `p4_multi_tf_confluence.py:33` · `p2_gold_macro_momentum.py` ·
`reproduce_exp00031.py:27`.

**It does not exist.** Therefore:

> **Every FX number in `ALPHA_SEARCH_TERMINAL_REPORT.md` — the entire basis of the project's
> central claim — is currently unverifiable and un-rerunnable.**

Compounding artifacts:
- `EXP-00025_traderdev_families.json` is **missing the `pnl_list`** that
  `run_traderdev_families.py:369` writes → per-trade t-statistics cannot be computed from the
  archive for the one FX candidate.
- `traderdev_fx_screen.py` returns only aggregates → the "power ≥ 60 trades" claim in
  `neg_results/EXP-00027...md` has **no supporting trade count anywhere in the repo**.
- `CRYPTO-001/002/003` bundles report 6, 4 and 3 OOS events against a manifest declaring
  2024-08-14 → 2026-08-14 coverage. Ingest truncation or a stub run — **undetermined.**

## 3. Coverage matrix — what TITAN has vs. what its strategies need

| Dimension | Have | Need | Gap |
|---|---|---|---|
| **Instruments** | EURUSD, GBPUSD, 1 more; G10 daily; XAUUSD; 35 FRED series; 13 ETFs (fixtures) | G10 full set for CS; 50+ equity names; crypto perps | **CRITICAL** for cross-sectional work |
| **Timeframe** | 5m, 1h, 4h, daily | Tick/L2 for microstructure | **CRITICAL** — the only classes with theorized edge |
| **History depth** | 12 months FX 4h; 8 years G10 daily; 2 days intraday | 15+ years for CS factors | **CRITICAL** for PEAD/momentum |
| **Resolution** | OHLCV bars | Trades / quotes / order book | **CRITICAL** for OFI, maker capture, session effects |
| **Source** | TWS (IBKR), Dukascopy, yfinance, FRED, Binance Vision, CSV | — | Mixed provenance; **no manifest hashes enforced for CSV** |
| **Quality** | `normalize.py:35`, `quality.py:37` validate OHLCV shape + business-day gaps | Session/gap/duplicate detection, cross-source reconciliation | **PARTIAL** |
| **Gaps** | 1,610 4h bars/yr measured, but `BARS_PER_YEAR = 2190` is used anyway | — | **Code contradicts its own data** |
| **Timestamps** | Dropped by `load_4h_closes` `traderdev_fx_screen.py:46-52` | Needed for session/regime work | **BLOCKS session analysis** |
| **Corporate actions** | Not found | Needed for equity factors | **MISSING** — EQ-001..008 on ETFs, unverified |
| **Spreads** | Real bid/ask in `run_traderdev_families.py`; hard-coded constants elsewhere | One sourced schedule | **CRITICAL** — the 0.9 bp vs 20 bp contradiction |
| **Bid/ask** | Dukascopy b/a decoder exists; feed not wired to runtime | Wired tick feed | **UNWIRED** |
| **Microstructure** | `dukascopy_bi5.py` decodes ticks; `FeatureGraph` consumes `Tick` | A tick producer | **NOTHING PRODUCES TICKS** |
| **Economic events** | FRED macro only | Earnings calendar for PEAD | **MISSING** — yet PEAD is the best artifact |
| **Macro** | 29 FRED CSVs + `macro_rates.py` ECB client (dead code) | — | Available |
| **Financing/swap** | `check_overnight_financing` exists in the risk path | Per-instrument swap series | **NOT IN RESEARCH HARNESS** — see H2 |
| **Liquidity** | none | ADV, spread, depth for capacity | **MISSING** — `capacity_proxy` in `results.py:73` is a weak proxy (avg trade value / avg equity) |
| **Borrow costs** | `total_borrow_cost` in EQ-002/006 bundles | Verified short-availability series | **UNVERIFIED** — short legs are 50% of the factor portfolios |
| **Regime labels** | `strategies/regime/` (ATR, etc.) | Historical regime series | **DEAD CODE** |

## 4. Can TITAN answer the questions its own strategies require?

| Strategy question | Answerable? |
|---|---|
| Does intraday FX momentum exist? | **No** — 2 days of intraday data |
| Do session effects exist? | **No** — timestamps dropped; `sig_session_ema` is `i % 6` |
| Is there order flow imbalance? | **No** — no tick feed |
| Does maker capture work? | **Yes** — CRYPTO-006 was well powered (4.87M fills) |
| Is FX carry real? | **No** — 27% power, cost constant 10× wrong, **no swap/financing data** |
| Does FX cross-sectional momentum work? | **No** — dataset absent, G10 daily is 92 KB |
| Does PEAD work? | **No** — **no earnings calendar**, no adjusted prices |
| What is the true cost of an EURUSD round turn? | **No** — 0.9 bp and 20 bp in the same repo, no source |

**8 of 8 questions TITAN's own strategies ask are currently unanswerable.**

## 5. What is genuinely necessary vs. what would be a wishlist

The brief warns against recommending expensive datasets without a clear experiment. Applying
that test strictly:

### NECESSARY — blocks an experiment that is already designed

| Data | Cost | Why necessary | Experiment it unblocks |
|---|---|---|---|
| **Restore `research/dukascopy_1m_ba/`** to disk | **Zero** — `scripts/pull_dukascopy_1m.py` and `convert_dukascopy.py` exist; data is free | The entire FX evidence base is unverifiable without it | **Reproduction of all 7 FX experiments** |
| **A sourced per-instrument cost schedule** | Zero | 0.9 bp vs 20 bp contradiction killed EXP-00022 | **Re-run EXP-00022/23/24** |
| **Session-preserving bar loader** | Zero — keep timestamps in `load_4h_cloxes` | `sig_session_ema` is not a session filter | Session-effect hypotheses |
| **Swap/financing series** for G10 | Near-zero (OANDA/Dukascopy free tier) | Carry strategies are structurally unrepresentable without overnight cost (HYPOTHESIS H2) | EXP-00023/24 re-run |
| **Earnings calendar + adjusted prices** for the EQ universe | Low (`yfinance` already a dependency) | PEAD is TITAN's best artifact and is untestable without it | **EQ-007 re-test** |
| **60+ equity names, 15+ years, adjusted** | Low (`yfinance`/free) | 13 ETFs × 2 years cannot support cross-sectional inference; 198 cells on 12 months is the overfitting source | CS factor work |

### NOT NECESSARY — do not buy

- **Tick/L2 for the whole market** — required only if the microstructure program is actually
  funded. `PIVOT_DECISION.md:24-27` already requires acquiring data BEFORE backtesting; that
  rule is correct and should be honoured rather than worked around.
- **Expensive vendor feeds** (Bloomberg/Refinitiv) — nothing in the evidence base justifies them.
- **Alternative data** — no demonstrated rationale.
- **More FRED series** — 29 exist, and macro factors already failed (P2).

### NOT WORTH IT AT ALL

- **The 2 days of `intraday_backtests`** — 2 days cannot test any intraday hypothesis. It is
  currently being used as if it could.

## 6. The three data decisions that unlock the most

1. **Restore the FX dataset** (zero cost, `.gitignore:101` is the only blocker) — converts 7
   experiments from *unverifiable* to *rerunnable*. Nothing else in this report has that ratio
   of cost to information.
2. **One cost schedule, one source, cited** — copy the epistemic posture of
   `Vibe-Trading/agent/backtest/engines/forex.py:37`: *"The XAU/USD figure is the median measured
   from Dukascopy tick data, 2017-2024 (~$0.32); the rest are typical retail quotes and should be
   overridden if you have better data."* Measured vs assumed must be labelled per instrument.
3. **Earnings calendar + adjusted prices** — PEAD is the only hypothesis with a clear causal
   mechanism *and* a positive measurement in the archive, and it currently has no data contract
   at all.
