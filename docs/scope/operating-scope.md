# Operating Scope — Initial Single-Domain Paper Trading

- **Status:** Extended by ADR-017 — intraday frequency added
- **Date:** 2026-07-13
- **Owner:** Developer
- **Review date:** Per Phase J gate and after any material change
- **Supersedes / extended by:** ADR-017 (adds intraday trading frequency)

## Purpose

Define the real-world boundaries for TITAN's first trading domain. This scope limits jurisdiction, asset class, venue, account type, frequency, hours, and strategy family so that all subsequent phases (data licensing, broker integration, risk controls, validation) operate against a single known environment. Expanding any boundary requires a new ADR and updated scope.

---

## Proposed scope

### Jurisdiction

**Recommendation: United States (SEC/CFTC regulatory framework).**

| Option | Analysis |
|---|---|
| **United States** | Largest selection of paper-ready broker APIs; USD base currency; extensive developer documentation; most broker sandboxes support US residents. SEC/CFTC framework is well-understood and most example code/trading literature assumes it. |
| European Union (MiFID II) | Stronger investor protections but fewer accessible paper APIs; currency fragmentation (EUR/GBP/CHF); PRIIPs/KID requirements for retail; broker sandbox support is weaker. |
| Other (APAC, etc.) | Requires separate analysis of local securities laws, exchange connectivity, and data residency. Not recommended for initial scope. |

**Default choice: United States.** All subsequent recommendations assume US jurisdiction.

### Asset class

**Recommendation: US-listed equities and ETFs.**

| Asset class | Suitability |
|---|---|---|
| **US equities & ETFs** | Simplest order semantics (no expiry, no contango/backwardation); highest liquidity; widest broker sandbox support; standard 9:30–16:00 ET session; no futures/forex complexity (rollover, margin rules, 24h sessions). |
| US options | Complex Greeks, expiry management, multi-leg order types. Not suitable for first scope. |
| Futures | Tick/point values, contract rollover, intraday margin, SOA limits, 23h+ sessions. Adds complexity without strategic necessity. |
| Forex | In-scope for simulated and backtest trading per ADR-014. Major pairs only, micro-lot convention (1 unit = 1000 base currency), no leverage, 24/5 calendar. Live forex requires a future IBKR adapter ADR. |
| Crypto | 24/7/365, different regulatory treatment, exchange-specific APIs. Excluded from initial scope. |

**Default choice: US-listed equities and ETFs for live trading; forex in-scope for simulated/backtest research.**

### Venue / Broker

**Recommendation: Alpaca (paper-first API) for initial paper trading; IBKR for future live expansion.**

See [broker-capability-register.md](broker-capability-register.md) for full capability register.

| Broker | Sandbox / Paper | API Type | Rate Limits | Paper Funding | Asset Classes | Order Types | Market Data | Assessment |
|---|---|---|---|---|---|---|---|---|
| **Alpaca** | Paper API — free, instant, resettable | REST + WebSocket (v2) | 200 req/min per key, 1000/day account creation | $100K simulated starting balance, configurable | US equities, ETFs, options (limited) | Market, limit, stop, stop-limit, trailing stop | Free IEX (delayed 15m), SIP (subscription) | **Best paper API.** Free tier, instant setup, reset on demand. Preferred for Phase J paper trading. |
| **Interactive Brokers (IBKR)** | IBKR Pro paper account — free but requires application | Client Portal Web API (REST), TWS/IBGW API (native) | 50 req/sec (Web API), 50 msgs/sec (TWS) | $1M simulated balance, monthly reset | Stocks, options, futures, forex, bonds, mutual funds | Market, limit, stop, stop-limit, MKT/LMT/STP combo, algo orders | Free delayed (15m), requires subscription + exchange fees for real-time | **Most capable broker.** But complex setup, application required, API documentation is dense. Better for Phase L+ live deployment. |
| **Tradier** | Brokerage API paper account — free, instant | REST API (v1) | 120 req/min, 5 req/sec | Paper account syncs with brokerage account status | US equities, options, ETFs | Market, limit, stop, stop-limit | Free delayed (15m), real-time via subscription | **Middle ground.** Simple REST API, instant paper, but fewer features than Alpaca or IBKR. |
| **TD Ameritrade (Schwab)** | No dedicated paper API since Schwab merger. API access restricted to existing brokerage clients. | REST (legacy, being deprecated) | 120 req/min | N/A — paper not available via API | US equities, options, ETFs | Market, limit, stop, stop-limit | Free delayed (15m), real-time with subscription | **Not recommended.** Post-merger uncertainty, no paper API, legacy API being phased out. |

### Account type

**Recommendation: Individual margin account.**

| Option | Analysis |
|---|---|
| **Individual margin** | Most flexible for paper — allows simulated short selling, increased buying power. For paper, margin settings only affect simulated P&L. Simplest tax treatment in live (no trust/corporate filing). |
| Individual cash | Restricts to settled funds. Unnecessary constraint for paper trading. |
| Joint / IRA / Corporate | Adds complexity (beneficiary rules, contribution limits, corporate filing). Not appropriate for initial solo paper trading. |

**Default choice: Individual margin account.**

### Trading frequency

Extended by ADR-017.

**Recommendation: Multiple timeframes (5m, 15m, 1h, 1d) for evaluation; orders placed only after closed-bar evaluation.**

| Frequency | Requirements | Assessment |
|---|---|---|
| **Daily (EOD)** | 1 bar/day per instrument. No intraday latency requirements. Simplest data licensing. Lowest API rate limit exposure. | Required. Foundation for swing strategies. |
| **Intraday (5m, 15m, 1h)** | Requires market data subscription, lower latency tolerance, session-aware bar processing. | Added by ADR-017. Only regular session (9:30–16:00 ET). Smallest certified paper notional. |
| High-frequency | Sub-second execution, co-location/proximity, direct market access. Out of scope for TITAN entirely. | Not planned. |

**Default choice: Multiple frequencies; each strategy declares its own trigger.**

**Activation gate:** An intraday (strategy, timeframe, parameters) tuple is disabled until walk-forward, Monte Carlo, fee/slippage, data-quality, and paper-session evidence is recorded and approved by Strategy Owner and Risk Owner per ADR-017.

### Trading hours

**Recommendation: US regular session only (9:30–16:00 ET) for intraday; daily evaluates after market close.**

| Session | Hours (ET) | Notes |
|---|---|---|
| **Regular** | 09:30–16:00 | Core liquidity, standard order books, all order types available. Intraday bars evaluated only during this window. |
| Pre-market | 04:00–09:30 | Lower liquidity, wider spreads, limited order types. Intraday bars excluded. Daily OHLCV may include pre-market data. |
| After-hours | 16:00–20:00 | Lower liquidity, no stop/stop-limit orders on most venues. Intraday bars excluded. Daily close evaluated after 16:00 ET. |

**Default choice: 09:30–16:00 ET, Monday–Friday, excluding US market holidays for intraday. Daily closes evaluated after 16:01 ET.**

### Strategy family

**Recommendation: Trend-following / moving-average crossover.**

| Strategy family | Suitability |
|---|---|
| **Moving-average crossover** | Already implemented as `MovingAverageCrossover` strategy in the codebase. Simplest to validate, test, and paper trade. Well-understood behavior — no black-box ambiguity. |
| Mean reversion | Requires different validation approach (stationarity tests, mean calculation windows). Possible Phase I (research) candidate. |
| ML / AI-driven | Heavy data and validation requirements. Contingent on Phase D+ advisory governance. Not appropriate for initial scope. |

**Default choice: Moving-average crossover on daily OHLCV.**

### Scope boundary

**Constraints that limit the initial operating envelope:**

- **One instrument at a time.** The paper trading domain operates a single-position strategy (one entry, one exit per cycle). Multi-instrument correlation, portfolio allocation, and pair strategies are explicitly out of scope.
- **Single-direction (long only).** No short positions initially. Short selling adds locate/borrow complexity, different margin treatment, and asymmetric risk. Shorting may be added in a later phase after long-only validation is mature.
- **No leverage or margin expansion.** Positions are sized against the paper account's cash balance. No borrowing, no day-trading leverage, no derivative margin.
- **US market holidays observed.** The system does not trade on days when US equities markets are closed.
- **No multi-leg orders.** Single-leg market and limit orders only.

### Forex-specific boundary

Expanded by ADR-014 for simulated and backtest trading only.

- **Four USD-quote pairs only.** EUR/USD, GBP/USD, AUD/USD, and NZD/USD. Non-USD-quote pairs, exotics, and crosses are excluded because USD-only portfolio valuation cannot safely value their PnL.
- **Micro-lot convention.** 1 unit = 1000 base currency; `step_size = 1000`; all order quantities must be multiples of 1000.
- **Simulated / backtest only.** IBKR paper and live forex execution are not approved. Any broker route requires accepted ADR-018 (or a superseding ADR), `Forex.spec.md`, paper-session evidence, and Architecture Council/Risk Owner approval.
- **No leverage.** Position sized against cash balance. No margin expansion for forex positions.
- **Existing strategies work unchanged.** Strategy code trading on price series (OHLC) needs no modification for forex symbols — only instrument registration changes.
- **Forex 24/5 calendar.** Weekdays are trading days (Mon–Fri). US market holidays are not observed. Saturday and Sunday are closed.

### Spot-gold boundary

- **XAUUSD only.** One troy ounce of spot gold quoted in USD.
- **Simulation and backtest only.** No Alpaca or live execution.
- **USD cash/PnL accounting** — quote currency is USD, no FX conversion needed.
- **One-ounce steps** — `step_size=1`, `tick_size=0.01`.
- **No leverage, financing, or rollover.**
- **Opening buys only** — a sell must reduce an existing long position.
- **Daily weekday bars** — 24/5 calendar with no holiday observance.

---

## Decision checklist

Items the developer must confirm before this scope takes effect:

- [ ] **Jurisdiction confirmed.** All relevant parties are US-based and the US regulatory framework applies.
- [ ] **Broker selected.** Paper broker account created and sandbox access verified.
- [ ] **Asset class confirmed.** US equities and ETFs are available in the selected broker's paper environment.
- [ ] **Account type confirmed.** Individual margin paper account opened.
- [ ] **Trading hours verified.** Strategy bars align with 09:30–16:00 ET session.
- [ ] **Scope boundary accepted.** Single-instrument, long-only, no leverage.
- [ ] **Data sources confirmed.** Daily OHLCV data available for the selected instrument from an authorized source.
- [ ] **Risk limits configured.** Paper account maximum position size, daily loss limit, and drawdown limit are set.
- [ ] **ADR created.** Any deviation from this scope is recorded in a new ADR.
- [x] **Forex scope expanded.** ADR-014 adopted — forex pairs in-scope for simulated/backtest trading with micro-lot convention.

---

## Open questions

1. **Multi-instrument when?** At what phase does TITAN expand to multi-instrument? After paper validation (Phase J) or only for live (Phase L)?
2. **Short selling inclusion.** Should short positions be added before or after multi-instrument? Short-first is riskier; recommend deferring until after long-only multi-instrument is validated.
3. **Options/derivatives.** Will options be needed for hedging or income strategies in a future phase? Recommend excluding until Phase M+.
4. **Data dependency on broker choice.** If Alpaca is the paper broker, can Polygon.io or IEX data be used for backtesting, or must the backtesting data source and paper data source match? (See [data-source-register.md](data-source-register.md) for provider analysis.)
5. **Holiday calendar source.** Which source defines the official US market holiday calendar? (Recommend: Nasdaq Trader / Cboe holiday calendars, verified at phase start.)
