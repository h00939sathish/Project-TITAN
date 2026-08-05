# Phase H — Scope, Legality, and Data Authority

> **Goal:** Establish the real-world constraints for a single paper-trading domain before collecting or acting on market data.

**Authority:** This phase follows NEWPLAN.md, adopted after PLAN.md completion. It produces documentation, registers, and templates — no code changes.

## Files to create

| Task | File | Description |
|---|---|---|
| H1 | `docs/scope/operating-scope.md` | Jurisdiction, asset class, venue, frequency, strategy family |
| H2 | `docs/scope/data-source-register.md` | Provider, license, permitted use, retention, corrections |
| H3 | `docs/scope/broker-capability-register.md` | Sandbox, auth, order semantics, rate limits, data entitlements |
| H4 | `docs/scope/threat-model.md` | Credentials, local dev, CI, deps, broker callbacks, prompt injection |
| H5 | `docs/scope/capital-policy.md` | Paper-only until Phase K, no external/client capital |
| H6 | `docs/scope/legal-briefing-questions.md` | Questions to take to legal/compliance counsel |

## Where this fits

Phase H is the first post-MVP phase from NEWPLAN.md. It grounds all subsequent research (Phase I), paper operation (Phase J), and live evaluation (Phases K–M) in a defined jurisdiction, asset class, data provenance, broker relationship, and risk posture. Nothing that follows works without this foundation.

## Phase exit gate

The operating scope, data entitlement, broker capability, security threat model, and capital prohibition are approved and stored with their review dates. Items requiring human legal/compliance input may be marked as "pending counsel review."

---

### Task H1: Define the initial operating scope

**File:** `docs/scope/operating-scope.md`

Draft a document that defines the initial single-domain scope. Since the developer must make the final choices, present options with analysis and recommend defaults.

Include:
- **Jurisdiction:** Recommend United States (SEC/CFTC regulatory framework, most broker sandboxes, USD base currency). Note that other jurisdictions require separate analysis.
- **Asset class:** Recommend US-listed equities and ETFs (simplest order semantics, highest liquidity, most broker sandbox support, no futures/forex complexity).
- **Venue/broker:** Survey 3–4 paper-friendly brokers (Interactive Brokers, Alpaca, Tradier, TD Ameritachi's API status). For each: sandbox availability, API type, rate limits, paper account funding, supported asset classes, order types, market data entitlements.
- **Account type:** Recommend individual margin account (most flexible for paper, simplest tax treatment).
- **Trading frequency:** Recommend daily (end-of-day bars, no intraday latency requirements).
- **Trading hours:** US regular session 9:30–16:00 ET.
- **Strategy family:** Recommend trend-following / moving-average crossover (already implemented as MovingAverageCrossover, simplest to validate).
- **Target strategy family scope boundary:** One instrument at a time, single-direction, no shorts initially.

### Task H2: Create data-source register

**File:** `docs/scope/data-source-register.md`

Create a register that tracks every data source the system might consume. For each:
- Provider name, source URL
- License type (free, CC, commercial, exchange)
- Permitted use (research, paper trading, live trading, redistribution)
- Restrictions (no redistribution, attribution required, rate limits)
- Retention period (how long cached data may be kept)
- Exchange/calendar coverage (which exchanges, trading calendars)
- Correction policy (does provider issue corrections? how to detect?)
- Owner (who is responsible for maintaining this relationship)
- Review date (when to re-verify terms)

Include realistic candidates: Yahoo Finance (free, no live trading), Polygon.io (commercial, paper+live), Alpha Vantage (free tier, limited), broker-provided data (Alpaca, IB).

### Task H3: Create broker capability register

**File:** `docs/scope/broker-capability-register.md`

Create a register that tracks what each candidate broker offers. For each:
- Broker name
- Sandbox/paper availability (free? funded? reset policy?)
- Authentication method (API key, OAuth, session token)
- Supported order types (market, limit, stop, stop-limit, etc.)
- Rate limits (requests/second, daily caps)
- Market data entitlement (free, subscription, exchange fees)
- Statement cadence (daily, monthly, real-time)
- Reconciliation coverage (what data is available for position/order reconciliation)
- Asset classes supported
- Account types supported (individual, joint, IRA, corp)
- API documentation quality
- Known limitations or quirks

Focus on brokers that are realistic for a solo US developer: Alpaca (best paper API, free tier), Interactive Brokers (most capable, complex), Tradier (brokerage API, paper available).

### Task H4: Perform threat model

**File:** `docs/scope/threat-model.md`

Perform a structured threat model for the current system. Use the STRIDE methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege). Cover:

1. **Credentials and secrets:**
   - Where are API keys stored today? (Nowhere — paper-only)
   - Where will they be stored in Phase K? (Recommend OS keychain/env vars/vault)
   - What prevents exposure in logs, prompts, error messages? (Currently nothing — mitigation needed)
   - CI/CD secrets management

2. **Local development environment:**
   - Python/Rust toolchain integrity
   - Dependency supply chain (PyPI, crates.io)
   - Development versus production isolation

3. **Broker callbacks/webhooks:**
   - Authentication of incoming webhooks
   - Validation of callback payloads
   - Replay attack protection

4. **Data poisoning:**
   - Market data provenance verification
   - Checksum validation on ingested data
   - Data quality gates (existing in Phase D)

5. **Prompt injection (AI phase):**
   - Separation of strategy advice from execution (already designed)
   - Output validation before promotion

6. **Operator access control:**
   - Single developer — no access control currently
   - What changes when moving to restricted-live?

For each threat, document: threat description, affected component, risk level (High/Medium/Low), current mitigation, recommended mitigation, priority.

### Task H5: Set explicit capital policy

**File:** `docs/scope/capital-policy.md`

A short, unambiguous policy document stating:

1. **Current status:** Paper trading only. No real capital is at risk.
2. **Prohibition:** External/client capital, leverage, margin expansion, and any form of third-party money management are strictly prohibited until Phase K exit gate is passed.
3. **Self-funding:** If the developer chooses to deploy personal capital in Phase L, the amount must be explicitly declared in the live experiment charter and must not exceed the stated maximum loss.
4. **Review:** This policy is reviewed at each phase gate and after any operational incident.
5. **Consequence:** Violation of this policy requires an immediate halt, incident review, and restoration of paper-only status before any further work.

### Task H6: Draft legal/compliance briefing questions

**File:** `docs/scope/legal-briefing-questions.md`

A document the developer can take to a legal professional. It does NOT provide legal advice — it asks the right questions. Include:

1. Personal trading vs. proprietary trading vs. advisory activity — which regulatory framework applies?
2. Do automated trading systems require registration as a commodity trading advisor (CTA) or investment advisor?
3. What are the record-keeping requirements for automated trading decisions?
4. What securities law restrictions apply to backtesting and paper trading?
5. If moving to self-funded live trading with <$X capital, what exemptions apply?
6. What are the data redistribution restrictions for market data providers?
7. What liability does the developer have for software bugs that cause trading losses?
8. What are the tax implications of automated trading (wash sales, short-term gains, etc.)?

Each question should include: why it matters, what the developer currently assumes, what evidence/action is needed.

## Acceptance criteria

- All 6 documents created under `docs/scope/`
- Operating scope defines at least: jurisdiction, asset class, venue/broker, account type, frequency, strategy family
- Data-source register lists at least 3 providers with license/permitted-use documentation
- Broker capability register lists at least 3 brokers with sandbox/API assessment
- Threat model covers all 6 STRIDE categories with risk levels and mitigations
- Capital policy is unambiguous and references NEWPLAN.md phase gates
- Legal briefing questions document is marked "NOT LEGAL ADVICE — for counsel preparation"

## Constraints

- No code changes — documentation only
- No credentials, keys, or secrets in any document
- Legal briefing document must NOT claim to provide legal advice
- Follow existing docs/ conventions
