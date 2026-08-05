# Legal/Compliance Briefing Questions

**THIS DOCUMENT IS NOT LEGAL ADVICE. IT IS A SET OF QUESTIONS FOR COUNSEL PREPARATION ONLY.**
**DO NOT RELY ON THIS DOCUMENT FOR COMPLIANCE DECISIONS. CONSULT A QUALIFIED ATTORNEY.**

- **Prepared by:** Developer (self-represented individual)
- **Date:** 2026-07-13
- **Status:** Draft — pending counsel review
- **Purpose:** Prepare for a meeting with a securities/commodities attorney. Each question explains why it matters, the developer's current assumption, and what evidence or action is needed.

---

## Instructions for use

1. Do not treat any of the following as legal conclusions. Every item is a question, not an answer.
2. Present this document to a qualified attorney in the relevant jurisdiction (assumed: United States).
3. Document the attorney's responses and record any compliance actions taken in an ADR.
4. Review this document quarterly and before any material change (Phase K live gate, addition of external capital, expansion to new jurisdictions).

---

## Questions

### Q1: Personal trading vs. proprietary trading vs. advisory activity

| Aspect | Detail |
|---|---|
| **Why it matters** | The regulatory framework determines registration requirements, record-keeping, disclosure obligations, and liability. Personal trading is least regulated; proprietary trading with a firm structure adds compliance; advisory/management of third-party capital triggers the highest regulatory burden. |
| **Current assumption** | The developer is trading their own capital (personal trading) with automated tools. No clients, no third-party money, no advisory service. |
| **Evidence / action needed** | Confirm that fully automated execution of the developer's personal strategy on the developer's own capital is personal trading under SEC/CFTC rules, not advisory or proprietary trading. Identify the point at which a tool that makes autonomous decisions crosses from "personal tool" to "investment adviser" under the Investment Advisers Act of 1940. |

---

### Q2: Registration requirements for automated trading systems

| Aspect | Detail |
|---|---|
| **Why it matters** | Operating an unregistered CTA or investment adviser is a federal offense. Even if the system only executes pre-programmed rules, there may be registration triggers depending on how the system is characterized and whether it ever manages external capital. |
| **Current assumption** | A solo developer trading their own capital with a fully automated system does not need CTA/IA registration. No solicitation, no advisory, no third-party management. |
| **Evidence / action needed** | Confirm the conditions under which an automated trading system triggers CTA registration under the Commodity Exchange Act (if trading futures/commodities) or investment adviser registration under the Advisers Act (if trading securities). Confirm that equities-only, self-capital, non-advisory automated trading does not require registration. |

---

### Q3: Record-keeping requirements for automated trading decisions

| Aspect | Detail |
|---|---|
| **Why it matters** | Even without formal registration, the SEC/CFTC may require records of trading decisions, order logs, and communications. Automated systems produce voluminous data that may or may not satisfy record-keeping rules. |
| **Current assumption** | TITAN's event log, order history, and reconciliation data constitute sufficient records. The developer retains all trading history. |
| **Evidence / action needed** | Identify record-keeping requirements that apply to automated personal trading (e.g., order records, timestamps, decision logs). Determine if the current event-driven architecture (event log with message types, timestamps, and actor identities) satisfies any applicable requirements. Ask whether book and records rules (e.g., SEC Rule 17a-3/17a-4, CFTC Regulation 1.31) apply to a solo developer trading personal capital. |

---

### Q4: Securities law restrictions on backtesting and paper trading

| Aspect | Detail |
|---|---|
| **Why it matters** | Even simulated trading may have legal implications if the system or its output is characterized as providing investment advice, or if backtesting data is used in a way that violates data licensing terms. |
| **Current assumption** | Backtesting and paper trading are internal development activities with no regulatory restrictions. Data source TOS (e.g., no redistribution, no commercial use) are the primary constraint. |
| **Evidence / action needed** | Confirm that backtesting and paper trading with a self-hosted system, using licensed data, does not trigger any securities law requirements. (This is distinct from performance reporting or marketing — TITAN does not publish backtest results.) Also confirm that paper trading through a registered broker's paper API (Alpaca/IBKR/Tradier) is covered by the broker's regulatory framework and does not require separate registrations. |

---

### Q5: Exemptions for small self-funded live capital

| Aspect | Detail |
|---|---|
| **Why it matters** | If the developer moves to live trading with personal capital below a certain threshold, there may be exemptions from registration, reporting, or other requirements that would apply to larger or externally funded operations. |
| **Current assumption** | Small personal capital trading (<$X) does not trigger registration. The developer understands which exemptions apply at which thresholds. |
| **Evidence / action needed** | Identify the relevant thresholds: (a) de minimis exemption under the Advisers Act ($25M AUM for federal registration, lower for state registration); (b) eligible contract participant thresholds under the Commodity Exchange Act; (c) pattern day trader rules under FINRA ($25K minimum equity). Also ask whether operating with a small account through a registered broker (e.g., Alpaca) provides any safe harbor or brokerage-mediated compliance. |

---

### Q6: Data redistribution restrictions

| Aspect | Detail |
|---|---|
| **Why it matters** | Market data providers (exchanges, consolidators, broker-dealers) restrict how their data may be used, cached, or redistributed. Violating these restrictions can result in account termination, legal liability, or loss of data access. |
| **Current assumption** | TITAN may cache market data for operational purposes (reconciliation, backtesting) but may not redistribute it. Alpaca/Polygon data is used only within TITAN and only for the developer's personal trading. |
| **Evidence / action needed** | Review the specific TOS/data agreements for each provider (Polygon.io, Alpaca, and any exchange subscriptions) with counsel. Confirm: (a) whether caching historical data for backtesting constitutes "redistribution"; (b) whether data used for live trading through Broker A may also be used for backtesting in the same system; (c) what retention limits apply to cached data. (See [data-source-register.md](data-source-register.md) for the current provider register.) |

---

### Q7: Liability for software bugs causing trading losses

| Aspect | Detail |
|---|---|
| **Why it matters** | A software bug in an automated trading system can cause financial loss — even if the developer is the only user. The developer should understand their personal liability exposure. |
| **Current assumption** | If the developer trades their own capital and a bug causes a loss, the loss is the developer's own (no third-party harm). No liability to third parties exists. |
| **Evidence / action needed** | Confirm: (a) whether the developer could face liability to their broker, exchange, or clearing firm for erroneous orders (e.g., fat-finger errors, runaway algorithms); (b) whether a software bug that causes a loss creates liability beyond the lost capital; (c) whether the broker's paper or live agreement contains provisions relevant to automated/systematic trading errors. Also ask about best practices for setting broker-side controls (order limits, velocity checks, kill switches) to limit liability. |

---

### Q8: Tax implications of automated trading

| Aspect | Detail |
|---|---|
| **Why it matters** | Automated trading generates frequent transactions with specific tax consequences. Wash sale rules, short-term vs. long-term capital gains, and the treatment of realized vs. unrealized gains all apply. |
| **Current assumption** | Standard US capital gains tax rules apply. TITAN's frequent trading will generate primarily short-term capital gains (taxed as ordinary income). Wash sale rules apply if the system repurchases the same instrument within 30 days of a loss sale. |
| **Evidence / action needed** | Confirm: (a) wash sale rule application for automated systems — does the system need to track wash sales across multiple accounts or only within the trading account? (b) whether the IRS's "trader vs. investor" distinction matters for a solo developer trading personal capital via automated means; (c) whether mark-to-market accounting under IRC §475(f) election is available or advisable; (d) estimated tax payment requirements for trading gains. This is primarily a tax preparation item but has compliance implications. |

---

## Next steps

1. [ ] Retain a qualified attorney with experience in securities law and automated trading.
2. [ ] Present this document as a briefing agenda.
3. [ ] Document counsel's responses and record in an ADR.
4. [ ] Update this document with any action items arising from counsel's advice.
5. [ ] Review before Phase K gate (live capital authorization).
