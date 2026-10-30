# Research data manifest

Audited 2026-10-21 against `master` (HEAD `8b554b6`). "Consumer" = code that reads the data today.

## Keep (decision evidence, tracked)

| Path | Size | Consumer | Notes |
|---|---|---|---|
| `research/neg_results/` | 52K | docs | Authoritative negative-results record (EXP-00016..00027, P2, P4). |
| `research/equities/` (EQ-001..008 bundles, preregs) | 252K | `equities_event_screen_007/008.py` | Re-run 2026-10-20 reproduced every bundle byte-for-byte except `generated_at`. |
| `research/crypto/hypotheses/`, `manifests/` | small | `crypto_screen.py` | CRYPTO-001..005 preregs + data manifests. |
| `research/crypto/results/` | 44K | `crypto_screen.py` | Sealed-verdict evidence; was gitignored, now tracked. |
| `research/results/` | 142K | scripts, docs | Aug 2026 results. Not invalidated by backtest fixes `0f73336`/`394b6ee` (none came from an exit-declaring strategy through ReplayEngine). |
| `research/fred/`, `fx_clean_5m/`, `gold_assets/`, `intraday_backtests/` | ~28M | archived scripts | Small, tracked, reproducibility inputs. |
| `research/prediction_markets/` | 12K | none yet | Active Phase-1 discovery (2026-10-16); untracked. |

## Raw caches (gitignored, regenerable, archived-research only)

| Path | Size | Consumer | Status |
|---|---|---|---|
| `research/dukascopy_1m_ba/` | 179M | 18 archived scripts | EURUSD/GBPUSD/AUDUSD 1m bid/ask, 2025-08..2026-07. **Timestamps are mislabelled** (bar ordinal instead of true minute; 6.4% EURUSD, 7.6% GBPUSD rows) — see below. Minute-level consumers must use `_corrected/`. |
| `research/dukascopy_1m_ba_corrected/` | 137M | `scripts/compare_dukascopy_volume.py` evidence | Relabelled copy of the set above; OHLC/volume/row-order unchanged. Regenerate with `scripts/relabel_dukascopy_timestamps.py` (reproduces the cited SHA-256 exactly). EURUSD `beacc2b8…f03811d`, GBPUSD `2f62938a…9c9f00f6` match `research/evidence/volume_source_20261029/comparison-timestamp-corrected-20261029.json`; AUDUSD `bbb3022e…c692003c`. |
| `research/dukascopy_1m_ba_prior/` | 901M | `wf_v2.py`, `exp_fx_002`, `run_fx00*` | EURUSD/GBPUSD/AUDUSD/NZDUSD 1m bid/ask, 2022-08-01..2025-07-31, built 2026-10-27 from the Dukascopy widget candle API. Audited: no Saturday bars, 0.005% zero-volume, per-weekday counts within 1-3 bars of the in-sample tick path, and 0 OHLC mismatches against the bi5 route on 190188 shared minutes. Known gap: EURUSD 2024-12-02..06 carries 1 bar/day (vendor hole). Provenance in `logs/dukascopy_jetta_20261027.job.json`. |
| `research/dukascopy_1m_ba_prior_bi5_partial/` | 51M | none | Superseded bi5 pull, stopped 2026-10-27. Kept only as the independent cross-check sample for the set above. |
| `research_data/intraday_5m/` | 116M | `scripts/run_eq_micro_001_backtest.py` | 54 equity 5m parquets incl. delisted names (RTN ends 2020-04-02 — correct). |
| `research/crypto/data/` | 94M | `crypto_screen.py` | Binance Vision dumps; checksums in `checksums*.json`. |

## Stale / out of sync

- `research_data/titan_research.db` — 31 runs dated 2026-07-23..30 (pre-WF-v2 protocol), still the default pool in `qualification.py`. Do not cite its metrics.
- `research/results/library.json` — holds only EXP-00001; `NegativeResultsLibrary` has no consumers. `neg_results/*.md` is the real record.
- `research/aspirational/carry_fxcarrvol/carry.py` — imports `titan.data.rate_differentials`, which does not exist.

## Known code gap affecting research replay

ReplayEngine-based research scripts (17, e.g. `research/replay_traderdev_ema9vwap.py`, `scripts/run_eq00*_core7.py`, `scripts/reproduce_exp00031.py`) fail outside pytest:
`PaperTradingEngine.submit_intent` requires an ADR-028 certificate that ReplayEngine never attaches. `tests/conftest.py` monkeypatches this away, so the suite stays green.

Reference re-run under the fixed engine (test-equivalent bypass, 4h, 2026-10-21): traderdev-ema9-vwap EURUSD +451 pips / GBPUSD +200 pips equity-based, 10 trades each, 17/13 rejected intents. Note `total_pnl` is cash-only and misreports runs that end in a position — use `final_equity`.

## Housekeeping done 2026-10-30

- Fixed `scripts/pull_dukascopy_1m.py`: timestamps now use the bar's true `minute` (was the bar's ordinal within the hour), HTTP 503 is retried instead of being read as "no data", and a 200 response with a short body is the only signal for a closed hour. Added `--candles` (2 requests/day, vendor 1m candles) and the Monday-Friday resume check.
- Added `scripts/relabel_dukascopy_timestamps.py` and its test, so the corrected tick set cited by the volume-source diagnostic is reproducible from the repo. Verified byte-identical hashes for EURUSD/GBPUSD.
- Deleted `research/fred/{IRSTCB01CHM156N,IRSTCB01NZM156N,IRSTCB01SEM156N,fx_DEXAUS,fx_DEXAUUS,fx_DEXNZUS}.csv`: the 2026-09-29 data audit found each was an HTML error page saved with a `.csv` name. They carried no observations, so nothing is lost; the NZD/CHF/SEK rate legs remain unavailable until a re-pull.

## Housekeeping done 2026-10-27

- Rebuilt `research/dukascopy_1m_ba_prior/` (deleted on 2026-10-21 above). Source is the widget candle API, not the bi5 datafeed — the bi5 daily-candle endpoint pads every closed minute with a flat zero-volume bar, which would have been ~29% of the file.

## Housekeeping done 2026-10-21

- Deleted (untracked, gitignored): `research/dukascopy_1m_ba_prior/`, `research/tws_daily/`, `research/tws_history/`, `research/cot/`, `quarantine-2026-09-20/`, empty `dukascopy_1m_ba/NZDUSD.json`, `research/__pycache__/`. Archived scripts that read them (e.g. `run_exp24_cot.py`, `run_regime_test.py`) need a re-pull before rerunning; `scripts/pull_dukascopy_1m.py` regenerates Dukascopy data.
- Stashed timestamp-only churn in EQ bundles: `git stash list` → `titan-eq-generated_at-churn-2026-10-21`.
