# Development Guide

> **Owner:** Developer Experience
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Architecture Council; Release Owner for workflow changes
> **Depends On:** [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md), [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md), [TESTING_STANDARD.md](TESTING_STANDARD.md)
> **Supersedes:** None
> **Review Frequency:** Per bootstrap/release change; quarterly otherwise

## First day

Read `AGENTS.md`, `OPERATING_PRINCIPLES.md`, `ARCHITECTURE.md`, `SYSTEM_CONTRACTS.md`, `RISK_POLICY.md`, and the relevant ADRs before changing a subsystem. Development credentials access only development/simulation fixtures; live credentials and broker capability are not part of local setup. The actual bootstrap command, toolchain versions, and configuration keys belong in a versioned implementation README once the codebase exists; this guide defines the required workflow without inventing it.

## Boot process

The eventual composition root loads typed configuration, validates schema and environment, initializes telemetry, checks storage/connectivity, registers contract consumers/producers, restores durable state, starts adapters in non-routing mode, performs reconciliation, and admits strategy intents only when the trading state is explicitly `ACTIVE`. A failure at any safety-critical step results in halted/no-route mode. This startup discipline follows the selected reconciliation/adoption evidence in `../ADOPTION_DECISIONS.md` and the recovery concerns in `../FAILURE_ANALYSIS.md`. See [EXECUTION_SPEC.md](EXECUTION_SPEC.md).

## Adding a strategy

Create a versioned package with declared instruments, data/feature requirements, parameter schema, deterministic signal logic, risk profile, expiry behavior, and test fixtures. It may emit `TradeIntent` only. Add unit, replay, simulation, walk-forward, Monte Carlo, and paper evidence as applicable; register its package digest; promote under `RESEARCH_PROTOCOL.md` and `IMPLEMENTATION_PLAYBOOK.md`. A strategy never imports a broker SDK or adjusts its own hard limits.

## Adding a broker or AI agent

A broker adapter implements the declared contract, credential isolation, status mapping, idempotency, precision/rate limits, timeout/retry rules, and reconciliation endpoints; validate it in sandbox/paper with contract and failure fixtures. An AI agent receives an explicit purpose, read-only or draft capability set, structured work-item schema, prompt/model version, evaluation set, observability, and kill/suspension control under `AI_GOVERNANCE.md`. Neither route permits a shortcut to production authority.

## Testing and release

Run the smallest relevant unit/contract tests while developing, then the mandatory integration, replay, chaos, performance, and documentation gates from `TESTING_STANDARD.md`. Review a change for contracts, ownership, failure behavior, telemetry, security, documentation, and ADR/RFC requirement. Release immutable artifacts through isolated simulation, paper, and approved live stages; verify dashboards/reconciliation and a rollback before enablement. Do not declare completion without fresh command output for the applicable checks.
