# Portfolio Engine

> **Owner:** Portfolio and Risk Engineering
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Portfolio Owner; Risk Owner for limits/allocation
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [RISK_POLICY.md](RISK_POLICY.md), [EXECUTION_SPEC.md](EXECUTION_SPEC.md)
> **Supersedes:** None
> **Review Frequency:** Per accounting/allocation change; monthly otherwise

## Authority

The Portfolio Engine is the deterministic projection of approved fills, cash movements, valuations, and corporate actions. It owns internal position, cash, PnL, exposure, margin, and attribution views; broker truth remains independently reconciled. It does not accept direct strategy writes. This isolates portfolio correctness from the mutable/shared-state risks in `../FAILURE_ANALYSIS.md`.

## Account and valuation model

Every account has legal entity, base currency, broker, venue permissions, margin model, settlement calendar, and risk scope. Positions are keyed by account, canonical instrument, lot where applicable, and currency. Values use fixed decimal money/quantity types, approved FX sources, valuation timestamp, and price-quality status. Maintain realized/unrealized PnL, fees/taxes/financing, cash, accrued items, gross/net/sector/factor exposure, buying power, initial/maintenance margin, and available capital separately.

## Allocation and attribution

Allocation consumes approved strategy/ensemble targets and deterministic constraints: capital budget, account eligibility, liquidity, costs, concentration, correlation, margin, turnover, and risk limits. It emits proposed allocation changes for Risk approval; it never promises fills. Attribution decomposes PnL and risk by account, strategy/package version, instrument, currency/FX, factor/regime where supported, execution cost, and corporate action. Unattributed or stale valuations are visible exceptions, not residuals silently absorbed.

## Multi-account and reconciliation behavior

No account’s cash, margin, positions, or permissions may offset another’s unless a versioned legal/portfolio policy expressly permits it. Cross-currency valuation preserves native and base-currency amounts with FX provenance. Apply fills and corporate actions idempotently from canonical events; replay rebuilds views. A broker snapshot discrepancy creates a reconciliation event and, when material, invokes [RISK_POLICY.md](RISK_POLICY.md) rather than directly editing the projection.

