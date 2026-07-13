# Risk Policy

> **Owner:** Chief Risk Office
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Risk Owner
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md)
> **Supersedes:** None
> **Review Frequency:** Per limit/control change; monthly otherwise

## Mandate

Risk is a deterministic, independently owned veto function. It protects capital and market integrity ahead of strategy opportunity, uptime, or delivery schedule. No AI component, strategy, broker adapter, or operator shortcut may bypass it. This policy incorporates the strongest evaluated pre-trade and portfolio-risk patterns while correcting the auto-reset and unwired-control defects described in `../RISK_ENGINE_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

## Controls

| Control | Enforcement point | Failure posture |
|---|---|---|
| instrument/account/session eligibility | before intent acceptance | reject |
| price, quantity, notional and rate limit | pre-trade gate and active-order manager | reject/cancel |
| position, gross/net, sector and correlation exposure | pre-trade and event-driven recheck | reduce or halt |
| drawdown, loss and volatility limits | portfolio risk engine | reduce or halt |
| data freshness and model/strategy package validity | intent admission | reject |
| broker connectivity, authentication and reconciliation | routing and lifecycle | halt routing |
| market impact, liquidity and concentration | deterministic sizing | resize or reject |

Limits are explicit, versioned, scoped (portfolio/account/strategy/instrument), and configured below hard organization limits. Kelly, VaR, correlation, regime, and impact models can inform a conservative bound; their output never overrides hard exposure, liquidity, loss, or operational limits.

## Risk pipeline

`TradeIntent → schema/integrity → strategy eligibility → market-data freshness → order limits → position/exposure → portfolio/drawdown → liquidity/impact → broker/session health → approved intent or reasoned rejection`. Persist every decision with inputs, rule/version, timestamp, correlation id, and reason codes. Re-evaluate active orders after material market, portfolio, limit, or broker state changes.

## Kill switch and circuit breakers

The kill switch is persistent, fail-closed, auditable, and enforced locally at the risk and execution boundaries. It never auto-resets. Trigger sources include operator action, material reconciliation drift, repeated broker/authentication failure, stale critical data, breached loss/exposure limits, anomalous rejection/fill behavior, or unavailable risk state. Its action is configurable by policy only: block new orders; cancel open orders where safe; transition the trading state to `REDUCING` or `HALTED`; preserve audit evidence; alert owners.

Release from `HALTED` requires broker/order/position/balance reconciliation, root-cause and scope assessment, verified control health, an approved rollback or remediation, and two authorized human approvals. Circuit breakers use bounded time windows, cooldowns, and explicit reset criteria; they are tested as part of the live route, not merely instantiated.

## Capital allocation and deployment

Strategy capital is allocated incrementally by independent portfolio/risk approval, evidence quality, liquidity, operational maturity, and concentration budget. Progression is simulation → paper → restricted live → scaled live. Each progression requires defined limits, monitoring, a stop condition, and rollback; positive backtests or LLM recommendations are insufficient. The accountable human approves live capital changes.

## Incident response

On uncertainty, prefer containment: halt new risk, retain facts, reconcile, communicate, and only then recover. Never repair balances or positions by editing a projection; reconcile from broker truth and recorded events. Handle credentials as an incident: revoke/rotate, isolate affected adapters, and preserve minimally necessary forensic records. Follow the operational sequence in `IMPLEMENTATION_PLAYBOOK.md`.
