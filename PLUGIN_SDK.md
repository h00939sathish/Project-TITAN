# Plugin SDK

> **Owner:** Core Platform Architecture
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council; Security Owner for sandbox policy
> **Depends On:** [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md), [SECURITY.md](SECURITY.md)
> **Supersedes:** None
> **Review Frequency:** Per SDK/capability change; quarterly otherwise

## Purpose and boundary

Plugins extend TITAN without weakening contract ownership, deterministic execution, or security. Supported extension points are broker adapters, market-data connectors, indicators/features, strategy packages, AI advisory agents, risk rule modules, and execution algorithms. A plugin is never an exemption from [AGENTS.md](AGENTS.md), [RISK_POLICY.md](RISK_POLICY.md), or [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md). The narrow capability model responds to the broad-tool-surface and unwired-control risks documented in `../AI_AGENT_COMPARISON.md` and `../FAILURE_ANALYSIS.md`.

## Manifest and lifecycle

Every plugin includes signed manifest: id, semantic version, type, publisher/owner, compatibility range, requested capabilities, configuration schema, contract schemas, dependencies/licenses, entry point, supported environments, resource limits, telemetry, migration, and deprecation policy. Lifecycle is `Discovered → Verified → Installed → Configured → Enabled → Suspended/Disabled → Removed`; installation verifies signature, provenance, compatibility, vulnerability policy, and least privilege before code loads.

## Type-specific contracts

Broker plugins implement [BROKER_SPEC.md](BROKER_SPEC.md). Indicator/feature plugins declare deterministic input/output schemas, lookback, state, point-in-time behavior, and golden fixtures. Strategy plugins follow [STRATEGY_ENGINE.md](STRATEGY_ENGINE.md). AI plugins use only typed advisory work items and [AI_GOVERNANCE.md](AI_GOVERNANCE.md). Risk plugins may evaluate bounded rules and return reasoned decision inputs but cannot alter hard-policy authority. Execution plugins may propose routing/algorithm behavior but only operate behind the approved execution/risk interfaces.

## Sandboxing and certification

Plugins run with isolated identity, explicit filesystem/network/process/tool permissions, quotas, timeout, memory/CPU limits, structured logging, and no inherited secrets. Live-capable plugins require source review, signature and SBOM, contract/compatibility tests, failure/timeout tests, security assessment, paper certification, owner/runbook, and staged activation. Disablement is immediate and preserves facts; plugins must not hold canonical trading state or prevent recovery.
