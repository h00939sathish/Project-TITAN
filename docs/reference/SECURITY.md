# Security Handbook

> **Owner:** Security Engineering
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Security Owner; Risk Owner for broker-capability controls
> **Depends On:** [GOVERNANCE.md](GOVERNANCE.md), [AI_GOVERNANCE.md](AI_GOVERNANCE.md), [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md)
> **Supersedes:** None
> **Review Frequency:** Per incident/access-model change; quarterly otherwise

## Security posture

Protect capital authority, credentials, market/research data, operational integrity, and auditability through least privilege, separation of environments, secure defaults, and observable controls. The historical secret-handling and excessive-tool-surface concerns in `../FAILURE_ANALYSIS.md` and `../AI_AGENT_COMPARISON.md` are explicit design inputs.

## Identity, secrets, and broker access

Use workload identities and an approved secret manager; no credentials in source, logs, prompts, fixtures, local defaults, or issue trackers. Broker secrets are scoped to the least account/environment/capability and segregated from research and AI identities. Rotate on schedule and immediately after suspected exposure. OAuth/token refresh runs in a hardened adapter boundary, stores only encrypted refresh material, validates issuer/audience/expiry, and fails closed on refresh/auth uncertainty. Human access uses MFA and short-lived credentials.

## Authorization and environment separation

RBAC grants role and environment-scoped capabilities, with separate duties for developer, researcher, operator, risk approver, security administrator, and auditor. Live order routing, limit changes, kill-switch release, and production deployment require distinct audited roles; no shared accounts. Development, simulation, paper, and live data/credentials/networks are isolated. Production may not make unrestricted outbound connections; egress is allow-listed by service and vendor.

## Data and platform protection

Encrypt data in transit with current TLS and at rest with managed keys; rotate keys and restrict decrypt rights. Classify data as public, internal, confidential, or restricted; apply minimization, retention, masking, and access logs. Sign immutable release artifacts; attest dependency/build provenance; pin and scan dependencies; remediate according to severity and exposure. Plugins/adapters run with narrow APIs, signed packages, filesystem/network/process isolation, quotas, and no inherited production secrets.

## Audit and incident response

Append audit records for identity changes, secret access, configuration/limit changes, approvals, deployment, tool invocation, and broker-capability use. Audit streams are write-restricted, monitored, and retained under policy. Suspected compromise triggers containment (revoke/rotate/isolate), evidence preservation, impact assessment, notification under applicable obligations, recovery, and post-incident corrective actions. Do not use an incident to relax controls or erase forensic evidence.

