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
| `research/dukascopy_1m_ba/` | 179M | 18 archived scripts | EURUSD/GBPUSD/AUDUSD 1m bid/ask. Keep while any FX re-test is planned. |
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

## Housekeeping done 2026-10-21

- Deleted (untracked, gitignored): `research/dukascopy_1m_ba_prior/`, `research/tws_daily/`, `research/tws_history/`, `research/cot/`, `quarantine-2026-09-20/`, empty `dukascopy_1m_ba/NZDUSD.json`, `research/__pycache__/`. Archived scripts that read them (e.g. `run_exp24_cot.py`, `run_regime_test.py`) need a re-pull before rerunning; `scripts/pull_dukascopy_1m.py` regenerates Dukascopy data.
- Stashed timestamp-only churn in EQ bundles: `git stash list` → `titan-eq-generated_at-churn-2026-10-21`.
