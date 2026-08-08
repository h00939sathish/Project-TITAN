# Broker Specification

> **Owner:** Execution Platform
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Execution Owner; Security Owner for authentication
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md), [SECURITY.md](SECURITY.md)
> **Supersedes:** None
> **Review Frequency:** Per adapter/broker semantic change; quarterly otherwise

## Canonical interface

Each broker adapter exposes the same typed, asynchronous contract. It translates to/from external APIs but never exposes vendor SDK objects beyond its boundary. All methods return typed result/error variants carrying correlation id, broker timestamp, and normalized reason code.

```text
authenticate(credentials_ref) -> Session
refresh(session) -> Session
place_order(ApprovedOrderIntent) -> BrokerOrderAcknowledgement
modify(BrokerOrderId, OrderAmendment) -> BrokerOrderAcknowledgement
cancel(BrokerOrderId) -> CancellationAcknowledgement
positions(AccountId) -> BrokerPositionSnapshot
holdings(AccountId) -> BrokerHoldingSnapshot
margin(AccountId) -> MarginSnapshot
quotes(InstrumentSet) -> QuoteSnapshot
orders(AccountId, QueryWindow) -> BrokerOrderSnapshot
fills(AccountId, QueryWindow) -> BrokerFillSnapshot
heartbeat() -> AdapterHealth
reconcile(AccountId, ReconciliationCursor) -> BrokerTruthSnapshot
```

`place_order` accepts only a durable approved intent; an adapter must preserve the client idempotency key or declare a compensating reconciliation design. `modify` and `cancel` are constrained by the order state machine in [EXECUTION_SPEC.md](EXECUTION_SPEC.md). Calls are capability-gated by account, instrument, order type, environment, and session state.

## Adapter declaration

An adapter publishes broker/API version; supported asset classes, venues, order types, TIFs and amendments; precision/lot/minimum rules; session/calendar; rate/concurrency limits; idempotency behavior; authentication/refresh/expiry; streaming/polling semantics; pagination/cursors; error taxonomy; maintenance behavior; and reconciliation coverage. Unsupported capability is a typed rejection at validation, never a best-effort vendor call.

## Authentication and health

Credentials are references to secret-managed material. Authentication and refresh follow [SECURITY.md](SECURITY.md); raw secrets never enter logs, events, or AI context. `heartbeat` reports connectivity, authenticated session expiry, market/order stream liveness, throttling, last broker timestamp, and capability degradation. Health degradation blocks new routing according to policy; it does not make the adapter pretend success.

## Reconciliation and certification

`reconcile` returns normalized orders, fills, positions, balances, margin, and cursor/coverage metadata for an explicit broker snapshot time. It is required at startup, periodically, after disconnect, and for ambiguous actions. Certify a broker through schema fixtures, sandbox/paper order lifecycle, duplicate/timeout/cancel/partial-fill tests, auth-expiry tests, rate-limit tests, restart/reconciliation tests, security review, operational runbook, and restricted enablement. Fincept informs connector design only; its stale-fork and broad-boundary lessons are captured in `../FINCEPT_DELTA_REPORT.md` and `../FAILURE_ANALYSIS.md`.

