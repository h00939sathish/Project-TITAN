# DATA GAP ANALYSIS — 2026-09-29

What data TITAN has, what its own strategies require, and what is missing.
Rule applied: no expensive dataset is recommended unless a concrete experiment justifies it.

---

## 1. What exists on disk (verified)

| Dataset | Files / Size | Range | Instruments | Columns / notes |
|---|---|---|---|---|
| research/fx_clean_5m/ | 3 JSON / 21M | 2025-08-01 → 2026-07-31 (EUR/GBP); AUDUSD only 2026-06 | EURUSD, GBPUSD, AUDUSD | timestamp UTC Z, OHLC **midpoint**, volume = tick count |
| research/fx_clean_daily/ | 3 JSON / 92K | same | same | OHLC(mid) |
| research/gold_assets/ | 2 JSON / 1.4M | XAUUSD 2000-08 → 2026-08; DBC 2006-02 → 2026-08 | XAUUSD, DBC | `date` (no tz); volume mostly 0 |
| research/fred/ | 27 CSV + 1 XML / 3.3M | DFF 1954→; ECBDFR 1999→; DEXUSEU 1999→; DFII10 2003→ | rates, FX, policy | **6 files are HTML error pages saved as .csv** (DEXAUS, DEXAUUS, DEXNZUS, IRSTCB01CHM/NZM/SEM156N) — breaks NZD carry leg |
| research/intraday_backtests/ | 12 CSV / ~1M rows | ~2 weeks each (2026-07) | EURUSD, SPY | FX volume = 0.0 |
| tws_approved/ | 4 CSV | 2026-07-27→30 | EURUSD, SPY | timestamp "20260727 17:15:00 US/Eastern" (non-UTC) |
| tests/fixtures/market/ | 14 CSV | 2019-2024 | SPY/QQQ/AAPL/MSFT/IWM/TLT/XLF/XLK | daily OHLCV |
| crypto / equities manifests | manifests only | claimed 2020-2026 | BTCUSDT etc. | **no raw data present** — bundles not reproducible from repo |

Missing directories referenced by ~20 scripts: research/dukascopy_1m_ba/,
dukascopy_1m_ba_prior/, tws_history/, tws_daily/ (backtest_per_timeframe.py:32-35,
run_exp21_tsm_daily.py:24, run_exp_00024_carry_vol.py:43).

## 2. Quality findings (research/data_quality_audit.py + spot checks)

- EURUSD 5m: 0 dupes, 0 crossed, but 614 unexplained 6-9 min gaps/yr (~2-3% missing bars);
  GBPUSD 702 gaps. AUDUSD 5m: severe holes (125/245/425-min gaps).
- Daily FX includes Sunday bars, excludes Saturday — plausible but unvalidated against a
  broker calendar (calendar_forex.py:4: "broker holiday observances vary — not modeled").
- **Timezone mixing CONFIRMED**: normalize.py forces UTC; crypto hard-rejects non-UTC
  (crypto.py:57-59); but tws_approved CSVs carry US/Eastern strings and TWSDataFeed passes
  raw `bar.date` unnormalized (tws_feed.py:53-60); polygon_feed.py:67 converts epoch via
  `date.fromtimestamp()` WITHOUT tz=UTC → local-date shift on non-UTC hosts.
- gold files crash the audit tool (KeyError 'timestamp' — files use `date`).
- EXP-FX-002 prior-window Dukascopy pull FAILED contract: EURUSD 56.94% missing, GBPUSD
  6,203-bar stub → shelved DATA-UNAVAILABLE (exp_fx_002/STEP0_VERDICT.md).

## 3. Can TITAN answer the questions its own strategies ask?

| Strategy question | Answerable today? |
|---|---|
| "Does the 4h traderdev family survive a fresh 12-month window?" | **NO** — longest 1h series on disk ≈ 3 weeks; 4h bars must be aggregated from 1h (bar_aggregator.py) |
| "What is the real spread for EURUSD/GBPUSD at 4h signal times?" | **NO** — fx_clean_* is midpoint; convert_dukascopy.py:15-18 destroys bid/ask; FxCostModel half_spread defaults to assumed 0.10/0.50 bps (fx_costs.py:64-77), not measured |
| "Does the 12-16 UTC short-rally effect persist out-of-sample?" | **NO** — needs the same 1m bid/ask + a new window |
| "Does XS momentum work across 10+ pairs?" | **NO** — 3 pairs of daily data; 1m/week FX from a claimed Yahoo pull whose files are absent |
| "Can ORB trade equities intraday?" | **NO** — tws_history/ absent; only ~2-week SPY slices |
| "What did carry earn net of swap?" | PARTIALLY — swap hardcoded -0.15 bps/day (fx_costs.py:52-54), not measured; NZD leg broken |
| "Is there order-flow/microstructure alpha in crypto?" | **NO** — manifests only, no raw TRADE/L2 files |
| "Are fills at 0.2bps commission + $2 min achievable?" | UNTESTED — no real broker fill audit exists (only the 1-share Alpaca cert) |

## 4. Missing data, ranked by demonstrated need (not wishlist)

1. **Multi-year 1h FX (4-6 pairs), free from Dukascopy** — unblocks: traderdev 4h
   validation on a fresh window (the ONLY surviving candidate), XS FX momentum across
   pairs, cross-pair cointegration panel, session-effect retest. Scripts already exist
   (scripts/pull_dukascopy_1m.py, dukascopy_bi5.py); the prior pull failed contract and
   needs re-pulling with verification. Cost: time only.
2. **1m bid/ask for the existing 2025-08..2026-07 window** — unblocks: measuring real
   spreads instead of assuming them; EXP-00019/25/26 cost economics; P4 re-test. Same
   source, same scripts.
3. **Equity universe daily data (≥50 names, survivorship-bias-free)** — unblocks
   cross-sectional factor research (the class barely tested: EQ-00x used small universes).
   yfinance already wired (equities_intraday.py); needs point-in-time discipline instead
   of adjusted-close only.
4. **Fix the 6 corrupt FRED files** — trivial re-download; unblocks carry-vol NZD leg and
   any AUD/NZD macro work.
5. **Real swap/financing series** — needed before ANY hold-overnight FX sim is believed.
   Only after 1-4.

NOT recommended now (no experiment justifies the cost): tick/L2 order-book feeds
(Databento/Polygon paid tiers) — the crypto evidence says the latency/fee wall kills retail
microstructure edge, and no surviving TITAN hypothesis requires L2; options/IV data — no
VRP strategy has been proposed, let alone pre-registered; news/economics-calendar feeds —
CM-001 exists but can be run with scheduled-release timestamps + price data alone.

## 5. Verdict

Data is a **secondary** bottleneck (after the broken promotion→paper seam) but it is the
bottleneck for the RESEARCH path: the single surviving candidate and the next strategy
class (cross-sectional) cannot be tested on what's on disk. Everything on the critical
path is free or already scripted — the gap is operational discipline (re-pull, verify,
freeze), not budget.
