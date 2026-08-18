# ADR-030: Authorize a bounded US Equities cross-sectional factor research program

- **Status:** Proposed (2026-08-16) — Architecture Council and Risk Owner review
- **Date:** 2026-08-16
- **Owners:** Research Platform, Architecture Council, Risk Owner
- **Decision scope:** US Equities and US ETFs data acquisition, cross-sectional factor simulation, and validation only
- **Supersedes / superseded by:** Complements ADR-0005, ADR-0006, ADR-026, ADR-028, and ADR-029; focuses research on TITAN's primary approved operational asset class (`docs/scope/operating-scope.md`)

## Context

Previous directional single-instrument searches on liquid FX and Crypto perps terminated with zero survivors due to spread friction, lack of cointegration, and noise mining. Project TITAN's primary authorized operational scope is **US Equities and US ETFs** via registered broker adapters (IBKR / Alpaca).

Single-asset directional signals on OHLCV candles fail to isolate true alpha from broad market beta. In contrast, **Cross-Sectional Factor Investing** ranks an $N$-instrument universe simultaneously, constructing dollar-neutral long/short portfolios (long top quantiles, short bottom quantiles) that eliminate market beta and exploit persistent relative pricing anomalies, dispersion, and factor premia.

## Evidence

- `docs/scope/operating-scope.md`: US Equities and ETFs are TITAN's primary production asset classes.
- `research/ALPHA_SEARCH_TERMINAL_REPORT.md`: Recommends cross-sectional factor models as the primary structural alternative to single-pair directional trading.
- Existing codebase has:
  - NYSE/NASDAQ calendar engine (`src/titan/data/calendar.py`).
  - Point-in-time data normalization and split/dividend adjustments (`src/titan/data/normalize.py`, `src/titan/backtest/corporate_actions.py`).
  - Hierarchical Risk Parity and dynamic allocators (`src/titan/strategies/hrp_allocator.py`, `allocator.py`).
  - Liquid US ETF market fixtures (`spy_2020_2024.csv`, `qqq_2020_2024.csv`, `tlt_2020_2024.csv`).

## Decision

1. Authorize a **research-only discovery program** for US Equities and US Sector/Asset ETFs. No automated live order routing or capital allocation is authorized by this ADR.
2. Register a frozen, point-in-time universe of liquid US Equities / Sector ETFs (SPY, QQQ, IWM, XLF, XLK, XLE, XLV, XLI, XLU, XLP, XLY, XLB, TLT).
3. Test only pre-registered cross-sectional factor hypotheses:
   - **`EQ-001` (Cross-Sectional Momentum):** 12-1 Month relative strength ranking with 1-month skip to prevent short-term reversal contamination.
   - **`EQ-002` (Cross-Sectional Short-Term Reversal):** 5-day / 1-week mean-reversion rank against peer group dispersion.
   - **`EQ-003` (Volatility-Adjusted Relative Value / Low-Vol):** Sharpe-weighted and inverse-volatility ranked relative value.
4. Enforce strict **Dollar-Neutral / Beta-Neutral** portfolio construction: long the top quantile and short the bottom quantile with equal gross dollar exposure, zero net dollar exposure, and realistic borrowing/financing fee modeling (e.g. 50 bps annual short borrow fee + 1 bps execution spread + $0.005/share commission).
5. Require at least 24 contiguous months of point-in-time data with corporate action adjustments. Enforce frozen IS/OOS partitions before evaluating out-of-sample data.
6. Terminal outcome is either one reproducible net-of-cost candidate eligible for a future shadow-only proposal, or an absorbing negative-result record.

## Alternatives and trade-offs

- **Single-Stock Directional Trading:** Rejected because directional market beta dwarfs idiosyncratic alpha and incurs high whipsaw losses.
- **Unhedged Long-Only Factor Tilt:** Rejected for initial alpha evaluation because it confounds equity risk premia (beta) with cross-sectional selection skill (alpha).
- **High-Frequency Intraday Equities:** Deferred until end-of-day/multi-day cross-sectional factor alpha is proven.

## Consequences

- **Positive:** Focuses research directly on TITAN's primary production asset class; neutralizes market regime swings; exploits verified academic and institutional factor methodologies.
- **Negative:** Requires short-borrow modeling; factor turnover can generate execution drag if rebalancing frequency is too high.

## Validation and operations

Required acceptance evidence:
- Frozen dataset manifest with SHA-256 checksums (`research/equities/manifests/us_equities_etf_v1.json`).
- Factor evaluation test suite verifying ranking monotonicity, dollar neutrality, and quantile spread returns.
- Pre-registered walk-forward evaluation artifacts (`EQ-001-prereg.json`, `EQ-002-prereg.json`, `EQ-003-prereg.json`).
- Evidence bundles with granular PnL attribution (gross selection, short borrow, commissions, spread, net).
