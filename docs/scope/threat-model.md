# Threat Model — TITAN Paper Trading System

- **Status:** Active — Phase H
- **Date:** 2026-07-13
- **Owner:** Developer / Security Engineering
- **Review frequency:** Before Phase K (live) gate; after any security incident; quarterly
- **Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)

## Purpose

Identify and document threats to TITAN's paper-trading system, including the live-trading transition. This model covers credentials, local development, broker callbacks, data integrity, prompt injection (future AI phase), and operator access control. Each threat has a risk level, current mitigation, recommended mitigation, and priority.

---

## Threat register

### T01: API key exposure in logs, error messages, or prompts

| Attribute | Value |
|---|---|
| **Category** | Information Disclosure |
| **Description** | Broker API keys, secrets, or data provider tokens are written to stdout/stderr, log files, error tracebacks, or LLM prompts. An attacker with filesystem access, log reader access, or prompt-injection capability could extract credentials. |
| **Affected component** | All subsystems — credential resolution, logging, error handling, AI advisory |
| **Risk level** | **High** (for live); **Medium** (for paper — paper credentials cannot route capital but expose the pattern) |
| **Current mitigation** | No broker credentials are stored or used in the current codebase (paper-only phase). The credential loader module exists as stubs only. |
| **Recommended mitigation** | 1. Implement a credential loader that reads from OS keychain (Windows Credential Manager, macOS Keychain) or environment variables — never from config files. 2. Add a log sanitizer that redacts known credential patterns before writing. 3. Block API keys from ever reaching the AI advisory subsystem (already designed per ADR-0007). 4. For Phase K, credential validation tests that assert no key appears in any log output. |
| **Priority** | **P1** (must implement before Phase K) |

---

### T02: Dependency supply chain attack (PyPI / crates.io)

| Attribute | Value |
|---|---|
| **Category** | Tampering, Elevation of Privilege |
| **Description** | A malicious package is introduced via a direct or transitive dependency (typosquatting, compromised maintainer account, dependency confusion). The attacker gains code execution in the development or production environment. |
| **Affected component** | All subsystems — `requirements.txt`, `pyproject.toml`, `Cargo.toml`, CI/CD pipeline |
| **Risk level** | **High** |
| **Current mitigation** | Standard Python/Rust packaging (lock files, virtual environments). No package pinning audit trail. |
| **Recommended mitigation** | 1. Pin all dependencies with exact versions (or lock files). 2. Use `pip-audit` or `cargo-audit` in CI to detect known vulnerabilities. 3. Review new dependencies before adding — prefer well-established packages. 4. For Phase K, add a Software Bill of Materials (SBOM) generator to CI/CD. 5. Run dependency diffs in PR reviews. |
| **Priority** | **P1** (implement before any external connectivity) |

---

### T03: Toolchain integrity (compromised Python/Rust toolchain)

| Attribute | Value |
|---|---|
| **Category** | Tampering, Elevation of Privilege |
| **Description** | A compromised Python interpreter, rustc compiler, or build tool (e.g., via a malicious Homebrew/chocolatey package or a compromised VS Code extension) injects code at build time. The attacker gains the same privileges as the developer. |
| **Affected component** | Development environment (local machine) |
| **Risk level** | **Medium** (single developer — limited blast radius; no production deployment yet) |
| **Current mitigation** | Standard toolchain installed from official sources. No formal verification of toolchain integrity. |
| **Recommended mitigation** | 1. Install Python and Rust only from official sources (python.org, rustup.rs). 2. Verify checksums/SHA hashes of downloaded installers. 3. Review VS Code extensions before installation — prefer official/popular extensions. 4. For Phase L (live), run builds in a CI/CD environment (GitHub Actions) rather than local, to separate the development environment from the deployment artifact. |
| **Priority** | **P2** (before Phase L) |

---

### T04: Development/production environment confusion

| Attribute | Value |
|---|---|
| **Category** | Spoofing, Elevation of Privilege |
| **Description** | A developer accidentally runs a live configuration against a paper broker, or vice versa. Paper credentials sent to a live endpoint, or live config applied to a paper test, causing data corruption or accidental live order placement. |
| **Affected component** | Configuration loader, broker adapter, deployment pipeline |
| **Risk level** | **High** (during any phase with live-capable credentials) |
| **Current mitigation** | No live endpoints exist — only paper. Paper and live are logically separated by different base URLs and different credential sets. |
| **Recommended mitigation** | 1. Environment identity check on startup — assert that the configured broker environment (paper vs. live) matches the current runtime intent, using an explicit env var (`TITAN_ENV=paper|live`). 2. Add a startup test that connects to the broker and verifies the account type (paper vs. live) before any order activity. 3. Log the environment identity at every startup. 4. Never store paper and live credentials in the same keychain namespace. |
| **Priority** | **P1** (before Phase K) |

---

### T05: Webhook/callback replay attack

| Attribute | Value |
|---|---|
| **Category** | Spoofing, Tampering, Repudiation |
| **Description** | A broker webhook (order fill notification, account update) is intercepted and replayed by an attacker. The system processes the same fill or update multiple times, corrupting position tracking and P&L. For paper trading, this is a data integrity issue; for live, it could cause erroneous position/sizing decisions. |
| **Affected component** | Webhook listener / callback handler |
| **Risk level** | **Medium** (paper); **High** (live) |
| **Current mitigation** | No webhook listeners are implemented yet. All broker interactions are via REST polling. |
| **Recommended mitigation** | 1. Authenticate incoming webhooks with HMAC signatures (shared secret). 2. Include a unique event ID in each callback and enforce idempotency (reject events with IDs already processed). 3. Add a timestamp window (reject events with timestamps older than N seconds). 4. Log all incoming webhooks for audit. |
| **Priority** | **P1** (implement before webhook integration) |

---

### T06: Market data poisoning — invalid or manipulated data

| Attribute | Value |
|---|---|
| **Category** | Tampering |
| **Description** | An attacker or compromised data provider sends invalid, delayed, or manipulated market data (e.g., erroneous trades, fake quotes, stale timestamps). The system acts on this data, potentially causing bad backtest results or incorrect paper/live trading decisions. |
| **Affected component** | Data ingestion pipeline, data quality gates (Phase D), strategy evaluation, risk controls |
| **Risk level** | **Medium** |
| **Current mitigation** | The Phase D data quality gates validate schema, null ranges, and basic bounds. No data provenance checks or cross-source verification. |
| **Recommended mitigation** | 1. Verify data provenance — log the source, fetch timestamp, and any correction indicator for every data point. 2. Implement checksum validation (if provider offers content hashes). 3. Cross-validate against a secondary source for the same instrument (e.g., compare Alpaca IEX data with Polygon.io for the same bar). 4. Set data quality thresholds — reject bars with improbable volume/price changes. 5. Log all data poisoning alerts and reject out-of-bounds data. |
| **Priority** | **P1** (before paper trading) |

---

### T07: Prompt injection — AI advisory subsystem producing harmful instructions

| Attribute | Value |
|---|---|
| **Category** | Elevation of Privilege, Tampering |
| **Description** | A future AI advisory subsystem receives a prompt that causes it to generate trading instructions that violate risk limits, position size constraints, or strategy boundaries. The execution core acts on these instructions without proper validation. |
| **Affected component** | AI advisory subsystem (future Phase D/Phase I), strategy evaluation, risk controls |
| **Risk level** | **High** (when AI advisory is online) |
| **Current mitigation** | AI advisory has no execution authority (designed per ADR-0007). Strategy advice is structurally separated from the execution pipeline. All AI output passes through deterministic risk validation before any action. |
| **Recommended mitigation** | 1. Maintain the architectural separation: AI may propose, humans and deterministic risk controls approve. 2. Validate all AI advisory output against the strategy's schema, parameter bounds, and limits. 3. Add an "advisory log" that records every AI proposal and its disposition (accepted/rejected/overridden). 4. For Phase L+, consider an independent "AI output validator" that runs a secondary risk check on AI-generated proposals. |
| **Priority** | **P2** (before AI advisory integration) |

---

### T08: Operator single-point-of-failure / no access control

| Attribute | Value |
|---|---|
| **Category** | Elevation of Privilege, Information Disclosure |
| **Description** | A single developer has full access to all credentials, code, and configuration. There is no access control, no audit of configuration changes, and no separation of duties. If the developer's machine is compromised, an attacker gains full control of the trading system. |
| **Affected component** | All subsystems — developer workstation, credential storage, deployment pipeline |
| **Risk level** | **High** (live); **Low** (paper — no capital at risk, but the pattern matters) |
| **Current mitigation** | Solo developer — no formal access control. Credentials are not stored locally (paper-only phase). |
| **Recommended mitigation** | 1. For Phase L+, implement role-based access (RBAC) or at minimum: read-only operator vs. deployer vs. admin. 2. Require signed commits and CI/CD for all deployment changes. 3. Use a secrets manager (e.g., HashiCorp Vault, GitHub Actions secrets, or cloud key store) rather than developer-local credential storage. 4. Audit all configuration and parameter changes. |
| **Priority** | **P2** (before Phase L) |

---

### T09: Rate limit abuse — unintentional or malicious

| Attribute | Value |
|---|---|
| **Category** | Denial of Service |
| **Description** | The system exceeds broker API rate limits, either through a bug (e.g., infinite retry loop, missing rate-limit backoff) or an intentional attack. The broker bans the IP address or revokes API access, halting all operations. |
| **Affected component** | Broker adapter, order management, data ingestion (if using broker data) |
| **Risk level** | **Medium** |
| **Current mitigation** | No broker adapter is connected yet. Rate-limit handling is not implemented in the adapter stubs. |
| **Recommended mitigation** | 1. Implement rate-limit awareness in the broker adapter — parse `429` responses, `Retry-After` headers, and enforce client-side rate limiting. 2. Add a circuit breaker that pauses API calls when approaching rate limits. 3. Log rate-limit events and alert when approaching limits. 4. Test rate-limit handling with paper API before live. |
| **Priority** | **P1** (before broker adapter integration) |

---

### T10: Credential leakage via CI/CD logs

| Attribute | Value |
|---|---|
| **Category** | Information Disclosure |
| **Description** | CI/CD pipeline logs or build artifacts contain environment variables, test credentials, or API keys. An attacker with access to the CI/CD platform (GitHub Actions logs, build artifacts) extracts credentials. |
| **Affected component** | CI/CD pipeline (GitHub Actions / equivalent) |
| **Risk level** | **Medium** (paper); **High** (live) |
| **Current mitigation** | No CI/CD pipeline with credentials exists. Only CI checks are in place (lint, typecheck, test). |
| **Recommended mitigation** | 1. Use GitHub Actions secrets for all credentials — never inline in workflow files. 2. Use `::add-mask::` to mask secrets in logs. 3. Restrict workflow permissions (read-only for most jobs, write only for publish jobs). 4. Audit CI/CD logs for accidental credential exposure. 5. Rotate CI/CD credentials regularly. |
| **Priority** | **P1** (before any credential is stored in CI/CD) |

---

## Risk summary

| ID | Threat | Risk (Paper) | Risk (Live) | Priority |
|---|---|---|---|---|
| T01 | API key exposure | Medium | High | P1 |
| T02 | Dependency supply chain | High | High | P1 |
| T03 | Toolchain integrity | Medium | Medium | P2 |
| T04 | Dev/prod environment confusion | Medium | High | P1 |
| T05 | Webhook replay | Medium | High | P1 |
| T06 | Data poisoning | Medium | Medium | P1 |
| T07 | Prompt injection | N/A (future) | High | P2 |
| T08 | Operator single-point-of-failure | Low | High | P2 |
| T09 | Rate limit abuse | Medium | Medium | P1 |
| T10 | CI/CD credential leakage | Medium | High | P1 |

## Phase gates

| Gate | Threat model action |
|---|---|
| **Phase J (paper trading)** | Mitigate T02, T04, T06, T09 before paper broker connection. T01 mitigations for paper credentials. |
| **Phase K (live gate)** | Mitigate all P1 items. Full threat model review. T01/T10 mitigations for live credentials. |
| **Phase L (live deployment)** | Mitigate all P2 items. T07 if AI advisory is online. T03/T08 for production environment. |
| **Incident response** | Any confirmed threat triggers a model update and re-review of affected threats. |
