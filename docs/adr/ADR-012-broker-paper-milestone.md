# ADR-012: Broker-Paper Certification Milestone

**Status:** Active  
**Date:** 2026-07-15 (updated)  
**Decision:** Wire AlpacaAdapter into a `broker-paper` mode with certification gates and fail-closed order routing.  
**Supersedes:** None  
**Depends on:** ADR-009 (Phase J scope), ADR-010 (fail-closed recovery)

## Context

Paper trading with a real broker (Alpaca paper account) is the validation gate before any live-capital work. The initial milestone (2026-07-14) certified read-only account access. The pipeline has since progressed to autonomous order placement with fail-closed safeguards.

## Decision

Introduce `--mode broker-paper` to the session runner. This mode:

1. **Instantiates AlpacaAdapter** configured for paper trading
2. **Rejects live credentials** — validates the base URL is a paper endpoint
3. **Requires approved data** — reuses the `paper-preflight` data validation (freshness, coverage, minimum history) or live data feed
4. **Routes approved intents to Alpaca** — the engine submits intents through AlpacaAdapter.place_order(), not read-only
5. **Enforces fail-closed** — any authentication failure, heartbeat loss, stale data, submit failure, reconciliation drift, or persistence error triggers the kill switch and prevents routing

### Safety controls in the order path

| Control | Location | Behavior |
|---|---|---|
| Session-hours gate | AlpacaAdapter.place_order() | Rejects orders outside 9:30-16:00 ET Mon-Fri, NYSE holidays |
| Daily order limit | AlpacaAdapter.place_order() | Max 20 orders/day, persisted atomically across restarts |
| Risk gate | engine.submit_intent() | Validates instrument, notional, quantity, position size, gross exposure, drawdown, daily loss, data freshness |
| Kill switch | engine._check_adapter_health(), reconcile(), _save_state() | Auto-triggered on broker disconnect, drift, fsync failure, or submit exception |
| Reconciliation drift | engine.reconcile() | Critical drift (severity >= 2) triggers kill switch, halts routing |
| Unfilled order guard | engine._resolve_fills() | Empty/zero fill quantity returns no fills — never books an accepted-but-unfilled order as filled |
| Atomic state writes | engine._save_state() | Write to tmp, fsync, replace; fsync failure triggers kill switch |
| Corrupt state detection | engine._load_state() | Unreadable or corrupt state file triggers kill switch on restart |
| Kill switch persistence | engine._save_state() | kill_switch_state and trading_state persisted in state file, restored on restart |
| Pre-validate timestamps | engine.submit_intent() | Invalid market_data_timestamp rejected before Rust risk gate |

## Certification gates

Before `broker-paper` mode can place an autonomous paper order, all gates must pass on the Alpaca paper account:

| Gate | Test | Evidence |
|---|---|---|
| Paper credentials | Validate base URL is `paper-api.alpaca.markets` | `test_rejects_live_endpoint` |
| Authentication | `authenticate()` returns CONNECTED session | `test_authenticate_paper` |
| Health/connectivity | `heartbeat()` returns connected | `test_heartbeat_paper` |
| Account state | `holdings()`, `positions()` return valid data | `test_read_account_state` |
| Kill switch | Auth failure → `submit_intent()` rejects | `test_auth_failure_halts` |
| Kill switch | Heartbeat loss → `submit_intent()` rejects | `test_heartbeat_loss_halts` |
| Kill switch | Stale data → startup halted | `test_stale_data_halts` |
| Rate limits | 200 req/min not exceeded under load | `test_rate_limit_respected` |
| Disconnect/reconnect | Session recovery after disconnect | `test_disconnect_reconnect` |
| Order submit | `place_order()` returns accepted | `test_submit_paper_order` |
| Order cancel | `cancel()` returns accepted | `test_cancel_paper_order` |
| Partial fills | Engine handles partial fill events | `test_partial_fill` |
| Restart | Event store replay → reconcile → resume | `test_restart_from_store` |
| Reconciliation | Daily recon against broker truth | `test_daily_reconciliation` |
| Kill switch persists | State file preserves kill_switch_state across restart | `test_kill_switch_persistence` |
| Unfilled order guard | Ack with no fill returns accepted=True, fills=[], order_state=accepted | `test_unfilled_order_not_booked` |
| Broker submit failure | AdapterError triggers kill switch | `test_submit_failure_triggers_kill_switch` |

## Implementation plan

1. Add `--mode broker-paper` to `scripts/paper_session.py`
2. Validate paper credentials in `_build_adapter()`
3. Wire `engine._check_adapter_health()` as the fail-closed gate
4. Write `tests/adapters/test_broker_paper_certification.py` with mocked + live tests
5. Run certification suite against Alpaca paper account
6. After certification: start read-only session for 14 days
7. After read-only: enable order placement with fail-closed controls

## Consequences

**Positive:**
- Clear boundary between simulation, preflight, and broker-connected modes
- Certification evidence proves readiness before any autonomous orders
- Fail-closed is enforced at every boundary
- Order path has multiple independent safety controls that persist across restarts

**Negative:**
- Requires Alpaca paper credentials in `.env` for certification tests
- Live tests depend on network connectivity and Alpaca API availability
- Certification gates add startup latency (auth + health check + data validation)

**Neutral:**
- broker-paper mode is gated: cannot accidentally start without proper credentials and data
- The same AlpacaAdapter code paths are used; no new adapter logic needed
- Order placement requires passing all safety controls; single point of failure does not bypass
