# Data Source Register

- **Status:** Active — Phase H
- **Date:** 2026-07-13
- **Owner:** Developer
- **Review frequency:** Quarterly; after any provider TOS change; before Phase K (live) gate

## Purpose

Track every data source TITAN may consume, their license terms, permitted uses, and restrictions. No data may be ingested without a matching register entry. No data may be redistributed without explicit permission. This register is the single source of truth for data authority.

---

## Register entries

### Yahoo Finance

| Field | Value |
|---|---|
| **Provider name** | Yahoo Finance (Yahoo/Verizon Media) |
| **Source URL** | `https://finance.yahoo.com/` (via `yfinance` community library) |
| **License type** | Free — no formal license. Data is publicly displayed, terms prohibit automated scraping for commercial use. |
| **Permitted use** | Research, personal use, backtesting (non-commercial). **Explicitly not permitted for live trading or any commercial/systematic deployment.** |
| **Restrictions** | No automated scraping in TOS; no redistribution; no commercial use; rate limiting enforced without notice. The `yfinance` library is community-maintained and has no SLA. |
| **Retention period** | Cached data may be retained for the duration of a research session. No permanent archival without independent verification of terms. Recommend 30-day cache TTL for research; do not use for production. |
| **Exchange/calendar coverage** | US equities (NYSE, NASDAQ, AMEX), ETFs; limited international. Trading calendar inferred — not guaranteed. |
| **Correction policy** | No formal correction policy. Adjustments (splits, dividends) may be applied silently. No notification mechanism. |
| **Owner** | Developer |
| **Review date** | 2026-10-13 (review quarterly; especially before any live data pipeline) |

**Notes:** Yahoo Finance is suitable for early research and prototyping only. It must not be the sole data source for any decision-making pipeline. The lack of SLA, TOS ambiguity for automated access, and silent correction policy make it unsuitable for paper or live trading.

---

### Polygon.io

| Field | Value |
|---|---|
| **Provider name** | Polygon.io (Polygon Technology, Inc.) |
| **Source URL** | `https://polygon.io/` |
| **License type** | Commercial — paid subscription tiers (Free, Basic, Starter, Development, Pro, Enterprise). |
| **Permitted use** | Research, backtesting, paper trading, and live trading (depending on tier). Free tier limited to research/paper. |
| **Restrictions** | No redistribution of raw data. API rate limits per tier (Free: 5 req/min; Basic/Starter: higher limits). Historical data depth varies by tier. Real-time data requires higher tiers. |
| **Retention period** | Cached responses may be retained for operational purposes (e.g., backtesting cache) but must not be redistributed. No specific retention limit defined in TOS — apply data-retention policy in capital-policy.md. |
| **Exchange/calendar coverage** | US equities (NYSE, NASDAQ, ARCA, BATS, IEX), options, forex, crypto. Trading calendars (market holidays, early closes) provided via API. |
| **Correction policy** | Polygon issues data corrections and provides a `correction` field on trades/quotes. Corrections are not retroactive for already-closed bars — consumers should detect via the correction indicator and re-derive affected bars. |
| **Owner** | Developer |
| **Review date** | 2026-10-13; before any subscription upgrade; before Phase K gate. |

**Notes:** Polygon.io is the recommended primary data source for paper trading and backtesting. The commercial tier removes the rate-limit and data-quality concerns of free sources. Correction indicators should be integrated into data quality gates.

---

### Alpha Vantage

| Field | Value |
|---|---|
| **Provider name** | Alpha Vantage (by IEX Cloud / independent operator) |
| **Source URL** | `https://www.alphavantage.co/` |
| **License type** | Free tier (API key based); premium tier available. |
| **Permitted use** | Research and personal use. Terms prohibit commercial use without a premium subscription. |
| **Restrictions** | 5 req/min (free tier), 500 req/day. No redistribution. Attribution required when displaying Alpha Vantage data. No guarantee of data completeness or correction notification. |
| **Retention period** | Cached data may be retained for personal use per TOS. Recommend same 30-day cache TTL as Yahoo Finance for free tier. |
| **Exchange/calendar coverage** | US equities, ETFs, forex, crypto. Trading calendar not provided — must be sourced separately. |
| **Correction policy** | No formal correction policy. Data is provided as-is with no correction notification mechanism. |
| **Owner** | Developer |
| **Review date** | 2026-10-13 |

**Notes:** Alpha Vantage free tier is suitable for early research but shares the same limitations as Yahoo Finance (rate limits, no SLA, no correction policy). The premium tier offers better terms but Polygon.io is preferred at comparable pricing.

---

### Alpaca Market Data (Alpaca Securities LLC)

| Field | Value |
|---|---|
| **Provider name** | Alpaca Market Data (Alpaca Securities LLC) |
| **Source URL** | `https://alpaca.markets/` |
| **License type** | Free with Alpaca brokerage account (no separate data subscription needed for IEX + delayed SIP). Real-time SIP requires subscription. |
| **Permitted use** | Trading and research through the Alpaca platform. Data may be used for order decisions executed through Alpaca. |
| **Restrictions** | Data is tied to the Alpaca brokerage relationship. No redistribution. Rate limits apply (200 req/min shared with trading API). Real-time SIP data requires a paid subscription + exchange fees. IEX data is free but may have gaps (IEX is a single dark pool with limited volume). |
| **Retention period** | No specific retention limit in TOS — Alpaca's data license agreements with exchanges likely restrict caching beyond operational needs. Recommend 24-hour operational cache only; do not archive Alpaca market data for backtesting. |
| **Exchange/calendar coverage** | US equities (NYSE, NASDAQ, ARCA, BATS, IEX, EDGX, MEMX). Trading calendar and market status API provided. |
| **Correction policy** | Alpaca uses exchange-provided data. Corrections are passed through from the exchange but no explicit Alpaca correction indicator. |
| **Owner** | Developer |
| **Review date** | 2026-10-13; before any real-time data subscription; before Phase K gate. |

**Notes:** Alpaca market data is the natural companion to Alpaca paper trading. The free IEX tier is sufficient for daily EOD strategies but has limitations (delayed, single-exchange source). For paper trading with the recommended Alpaca broker, this is the practical default data feed. However, backtesting should use a separate data source (Polygon.io or historical Parquet files) to avoid look-ahead bias.

---

### Interactive Brokers Market Data (IBKR)

| Field | Value |
|---|---|
| **Provider name** | Interactive Brokers Market Data |
| **Source URL** | `https://www.interactivebrokers.com/` |
| **License type** | Commercial — requires IBKR account. Real-time data requires subscription + exchange fees. Delayed data is free. |
| **Permitted use** | Trading and research through the IBKR platform. Data may be used for order decisions executed through IBKR. |
| **Restrictions** | No redistribution. Data subscriptions are per-user and per-exchange. Sub accounts in a master account may share data (terms vary). Data may not be used for non-IBKR trading decisions. |
| **Retention period** | Per IBKR data agreements, cached data may be retained for operational use during the trading session. Long-term archival for backtesting is restricted by exchange agreements. |
| **Exchange/calendar coverage** | Comprehensive — 150+ exchanges globally. Trading calendar provided. |
| **Correction policy** | Exchange-level corrections are passed through. IBKR provides a correction feed for trades but it must be explicitly subscribed to. |
| **Owner** | Developer |
| **Review date** | 2026-10-13; before Phase K gate. |

**Notes:** IBKR market data is the most comprehensive option but comes with the most complex licensing and cost structure. It is not recommended for initial paper trading (use Alpaca + Polygon.io instead). If IBKR is selected as the live broker in Phase L, its data feed would become the source of truth for execution.

---

## Provider comparison summary

| Provider | Cost | Permitted Use | Live Trading | Rate Limits | Correction Policy | Recommendation |
|---|---|---|---|---|---|---|
| Yahoo Finance | Free | Research only | No | Implicit/aggressive | None | **Research only.** Replace before Phase J. |
| Polygon.io | Free–$$/mo | Research, paper, live | Yes (paid tier) | 5/min (free), higher paid | Correction flag provided | **Primary data source.** |
| Alpha Vantage | Free–$ | Research, personal | No (free tier) | 5/min (free) | None | **Research fallback.** |
| Alpaca Market Data | Free (with account) | Paper trading, live | Yes (Alpaca only) | 200/min (shared) | Exchange passthrough | **Paper trading feed.** |
| Interactive Brokers | Subscription + fees | Trading through IBKR | Yes (IBKR only) | 50 req/sec (Web API) | Exchange passthrough | **Live execution feed.** |

---

## Data authority chain

For the initial paper-trading scope (single instrument, daily bars, Alpaca broker):

1. **Backtesting:** Polygon.io or pre-validated Parquet files. Yahoo Finance/Alpha Vantage for early research only.
2. **Paper trading execution:** Alpaca Market Data (free IEX tier for daily bars; sufficient for EOD strategy).
3. **Reconciliation:** Alpaca paper account positions/trades (source of truth for paper P&L).
4. **Live trading (future Phase L):** IBKR or Alpaca paid market data feeds.
