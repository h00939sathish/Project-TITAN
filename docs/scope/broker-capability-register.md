# Broker Capability Register

- **Status:** Active — Phase H
- **Date:** 2026-07-13
- **Owner:** Developer
- **Review frequency:** Before broker selection; before Phase K (live) gate; before adding a new broker

## Purpose

Track candidate brokers, their paper/sandbox capabilities, authentication, order semantics, rate limits, market data, and known limitations. This register supports the broker selection decision in Phase H1 (operating scope) and informs broker adapter implementation in Phase E.

---

## Register entries

### Alpaca (Alpaca Securities LLC)

| Capability | Assessment |
|---|---|
| **Broker name** | Alpaca Securities LLC |
| **Sandbox / paper availability** | **Free, instant, resettable.** Paper API credentials generated from the dashboard. No application process. Paper account can be reset with a single API call (clears all positions, orders, and resets balance). Starting balance configurable (default $100K simulated). |
| **Authentication method** | API key + secret key (base64-encoded, sent as `Apca-Api-Key-Id` and `Apca-Api-Secret-Key` headers). OAuth available for third-party apps. Credentials are environment-specific (paper vs. live use different API base URLs and key pairs). |
| **Supported order types** | Market, limit, stop, stop-limit, trailing stop (`trail_percent`). Day, good-till-cancelled, immediate-or-cancel, fill-or-kill time-in-force. One-cancels-other (OCO) bracket orders supported. |
| **Rate limits** | 200 requests per minute per API key. 1,000 account creation requests per day. WebSocket connections: 1 per API key (paper), multiple per key (live with approval). Throttling returns HTTP 429 with `Retry-After` header. |
| **Market data entitlement** | **Free:** IEX data (delayed, single exchange — low liquidity coverage for some instruments). **Subscription:** US equities SIP (real-time, all exchanges), options data. Real-time requires exchange fee payment. Historical data up to 15+ years via Polygon.io (Alpaca is a Polygon.io reseller). |
| **Statement cadence** | Daily trade confirmations (via API). Monthly account statements. No PDF statement generation — data retrieved via API. |
| **Reconciliation coverage** | Full position and order history via REST API. `positions`, `orders`, `account`, `activities` endpoints provide complete data for reconciliation. Trade confirmations available for each fill. |
| **Asset classes supported** | US equities, ETFs, options (limited — pending regulatory expansion). No futures, no forex, no fixed income. |
| **Account types supported** | Individual, joint, IRA (traditional, Roth, SEP), trust, corporate, partnership, LLC. All account types support paper trading. |
| **API documentation quality** | **Excellent.** OpenAPI specification available. Comprehensive documentation with examples. Active developer community and SDKs in Python, TypeScript, Go, Rust, etc. |
| **Known limitations / quirks** | Paper and live use the same API endpoints but different base URLs and separate API key pairs. Paper trading does not simulate short locate/borrow fees. Options support is still limited (calls/puts on major indices/ETFs only). IEX data has gaps — not all instruments trade on IEX. No futures or forex. Paper API occasionally diverges from live (e.g., fill simulation may be optimistic). |

---

### Interactive Brokers (IBKR)

| Capability | Assessment |
|---|---|
| **Broker name** | Interactive Brokers LLC |
| **Sandbox / paper availability** | **Free but requires application.** IBKR Pro paper account created via the IBKR account management portal. Requires a real IBKR account (funded or unfunded). Paper account balance defaults to $1M simulated, reset monthly. TWS/Gateway must be running for API access (local application). No instant/reset-on-demand — paper account resets at month end or on request. |
| **Authentication method** | **Client Portal Web API:** username/password + OTP/2FA (session-based). **TWS/IBGW API:** local socket connection (no auth beyond "trusted IPs" list in TWS/Gateway settings). Credentials are host-restricted — API must connect from a pre-approved IP address. This is a significant operational complexity. |
| **Supported order types** | Market, limit, stop, stop-limit, MIT (market-if-touched), LIT (limit-if-touched), trailing stop, trailing stop-limit, relative, pegged-to-market, pegged-to-stock, VWAP, TWAP, adaptive, iceberg/disclosed quantity, and many more. Complete algo order suite. |
| **Rate limits** | Web API: 50 requests per second (burst), 10 req/sec sustained recommended. TWS API: 50 messages per second. Historical data requests: 60 per minute per contract. More restrictive than Alpaca — overage results in connection drop or data back-off. |
| **Market data entitlement** | **Free:** delayed data (15 min) for US equities. **Subscription:** real-time data requires per-exchange subscription fees ($1.50–$10/mo per exchange + waiver fees). Snapshot data (2–5 minute delayed) available for small fee per request. Comprehensive global coverage. |
| **Statement cadence** | Daily activity statements (PDF and CSV via email or FTP). Monthly statements with full detail. Real-time account values via API. Trade confirmation reports. |
| **Reconciliation coverage** | Full account, positions, trades, orders, and transaction history via both Web API and TWS API. `portfolio/positions`, `trades`, `transactions` endpoints. Flex queries allow custom report generation. Most comprehensive reconciliation data of any retail broker API. |
| **Asset classes supported** | Stocks, ETFs, options, futures, forex, bonds, mutual funds, warrants, structured products, crypto (limited jurisdictions). Global exchange access. |
| **Account types supported** | Individual, joint, IRA (traditional, Roth, SEP, rollover), trust, corporate, partnership, LLC, advisor, institutional. |
| **API documentation quality** | **Dense and complex.** Multiple API surfaces (Client Portal Web API, TWS API, IBGW API, third-party API). Documentation is thorough but fragmented. Significant learning curve. The "official" Python SDK (ib_insync) is third-party — IBKR does not maintain an official Python SDK. |
| **Known limitations / quirks** | The TWS/Gateway requirement is the single largest operational friction — it must be running at all times for API access. The paper account freezes positions between monthly resets (cannot easily reset mid-month). Rate limits are strict and enforced by connection drop. Historical data is limited to 6–12 months for most contracts via API (IBKR's historical data is not a backtesting database). Paper trade fills are matched against the NBBO snapshot at submission time and may be more optimistic than live fills. Web API is relatively new (2022) and has fewer features than TWS API. |

---

### Tradier

| Capability | Assessment |
|---|---|
| **Broker name** | Tradier Inc. |
| **Sandbox / paper availability** | **Free, instant.** Paper account created via Tradier Brokerage API. Account is funded with $1M simulated balance. Paper account syncs with brokerage account status (resets when real account resets). No application process for API access — sign up and receive keys. |
| **Authentication method** | Bearer token (JWT) in Authorization header. Token is account-scoped. Paper and live use different tokens and API base URLs. Simpler than IBKR, similar to Alpaca. |
| **Supported order types** | Market, limit, stop, stop-limit. Day, GTC, fill-or-kill time-in-force. Multi-leg options orders supported (spreads, straddles, etc.). No trailing stop natively (must be calculated client-side). |
| **Rate limits** | 120 requests per minute, 5 requests per second. Returns HTTP 429 on overage with rate-limit headers. Comparable to Alpaca. |
| **Market data entitlement** | **Free:** delayed data (15 min) for US equities and options. **Subscription:** real-time data available via add-on subscriptions (equities, options, streaming quotes via WebSocket). Options data is a Tradier strength — free option chains in the API. |
| **Statement cadence** | Monthly statements (PDF and CSV). Trade confirmations available in the dashboard. API access to account history, positions, and orders. |
| **Reconciliation coverage** | Full position, order, and account history via REST API. `account`, `positions`, `orders`, `history` endpoints. Options positions are well covered. Trade confirmations (fills) available via `events` endpoint. |
| **Asset classes supported** | US equities, ETFs, options (strong). No futures, no forex, no fixed income. |
| **Account types supported** | Individual, joint, IRA (traditional, Roth), trust, corporate, partnership, LLC. |
| **API documentation quality** | **Good.** Swagger/OpenAPI specification available. Clear documentation with curl examples. Smaller community than Alpaca or IBKR but well-maintained. WebSocket streaming docs are less comprehensive than REST docs. |
| **Known limitations / quirks** | No trailing stop order type (client-side calc required). No native bundles/algo orders. Paper API does not simulate some order types well (e.g., complex option orders may fill immediately rather than at market). API access requires a funded brokerage account (minimum deposit to open the real account). Less active development than Alpaca. |

---

## Broker comparison summary

| Criteria | Alpaca | IBKR | Tradier |
|---|---|---|---|
| **Paper availability** | Instant, free, resettable | Requires app, monthly reset | Instant, free |
| **Authentication** | API key + secret | Username/password + OTP, or socket | Bearer token (JWT) |
| **Order types** | Standard + trailing stop, bracket | Full suite + algos | Standard + multi-leg options |
| **Rate limits** | 200/min | 50 req/sec Web, 50 msgs/sec TWS | 120/min, 5/sec |
| **Market data (free)** | IEX delayed | 15-min delayed | 15-min delayed |
| **Market data (paid)** | SIP real-time | Exchanges + subscription | Subscription |
| **Options** | Limited | Full | Full |
| **Futures / Forex** | No | Yes | No |
| **Operational complexity** | Low | High (TWS/Gateway) | Low |
| **API docs** | Excellent | Dense / fragmented | Good |
| **Best for** | Paper-first, rapid iteration | Full-featured live deployment | Options-heavy strategies |

## Recommendation

For the initial paper-trading scope (Phase J):

**Primary: Alpaca** — lowest operational overhead, instant paper, best developer experience, free tier sufficient for daily EOD strategies.

**Secondary (monitor for Phase L): IBKR** — most capable broker for live deployment but adds significant complexity. Do not adopt until paper-trading validation is mature.

**Tertiary: Tradier** — viable alternative if options trading is needed before IBKR integration. Otherwise, Alpaca covers the initial scope.

---

## Open questions

- Alpaca paper fill simulation: how realistic is it compared to live fills for limit orders? Need to run a parallel paper/live comparison before Phase L.
- IBKR Web API v TWS API: which should the Phase E adapter target? (Web API is simpler but has fewer features; TWS API is comprehensive but requires Gateway.)
- Tradier minimum deposit: what is the minimum funding required to maintain API access for paper-only development? (Currently unclear from public documentation — must confirm during broker onboarding.)
