# Capital Policy

- **Status:** Active — Phase H
- **Date:** 2026-07-13
- **Owner:** Developer
- **Review frequency:** Each phase gate; after any operational incident
- **Depends on:** NEWPLAN.md phase gates, [operating-scope.md](operating-scope.md)

## Policy

### 1. Current status

TITAN operates exclusively as a **paper trading system**. No real capital is at risk. All positions, balances, and P&L are simulated. This status holds until the Phase K exit gate is passed and a subsequent ADR authorizes live capital.

### 2. Prohibition

The following are **strictly prohibited** until Phase K exit gate is passed:

- **External/client capital.** No third party may contribute capital, directly or indirectly.
- **Leverage or margin expansion.** Positions may not exceed the paper account's available cash balance.
- **Third-party money management.** TITAN may not manage money on behalf of any person or entity.
- **Any form of live trading** using real capital, regardless of amount.

This prohibition extends to all environments (development, CI/CD, testing). Any code path that could route a live order without explicit human approval is a violation.

### 3. Self-funding

If the developer chooses to deploy personal capital in Phase L (or later), the following conditions apply:

- The **capital amount must be explicitly declared** in the live experiment charter (see NEWPLAN.md Phase L gate).
- The declared amount **must not exceed the stated maximum loss** defined in the charter.
- The capital must be the developer's own funds. No borrowed, leveraged, or third-party funds.
- The declaration is recorded in an ADR and signed off at the Phase L gate.

### 4. Review

This policy is reviewed at:

- **Each phase gate:** the policy is re-read and confirmed as still applicable.
- **After any operational incident:** the policy is reviewed and updated if the incident reveals a gap.
- **Quarterly:** standing review even if no incidents occur.

### 5. Consequence of violation

Violation of any provision of this capital policy requires:

1. **Immediate halt** of all TITAN operations.
2. **Incident review** — documented in the incident log with root cause, impact, and corrective actions.
3. **Restoration of paper-only status** — removal of any live credentials, funding, or configuration.
4. **Re-verification** at the Phase K gate before any further work.

## Authority

This policy is adopted under the authority granted by NEWPLAN.md and supersedes any prior informal capital arrangements. It may only be amended by a new ADR that references this document and explains the material change.
