# ADR-0007: AI advisory policy

- **Status:** Accepted
- **Date:** 2026-07-13
- **Owners:** AI Governance Lead, Risk Owner
- **Decision scope:** AI tooling, provider access, prompt authority
- **Supersedes / superseded by:** None

## Context

The R&D evidence establishes that AI in a trading system must be strictly advisory with no capital authority. The evaluated repos show varying patterns: LLM_trader's bounded reflection and structured output are usable; TradingAgents' LLM-as-risk-manager is dangerous; Fincept's broad tool surface is an anti-pattern.

## Evidence

- `EVIDENCE_SYNTHESIS.md` §7: LLM_trader contributes the strongest bounded AI patterns; TradingAgents' LLM risk delegation is rejected.
- `../AI_AGENT_COMPARISON.md`: prohibited patterns (LLM risk evaluation, regex parsing of model output, broad provider/tool surface).
- `../AI_GOVERNANCE.md`: AI is advisory only; deterministic validators override model output.

## Decision

1. **AI is deferred until after Phase F.** No AI capability (research agent, hypothesis generator, vector memory, reflection) is implemented until the deterministic capital path is proven in paper operation.
2. **When implemented, AI will be strictly advisory.** Agents receive explicit allow-listed tools, least-privilege identity, structured work-item schemas, and deterministic validators that override model output on schema, policy, factual-source, numeric, permission, and safety failures.
3. **No LLM call on the capital path.** The risk gate, execution engine, portfolio projection, and reconciliation contain zero model inference.
4. **Vector memory is advisory only.** It stores evidence pointers, hypotheses, and experimental results. It never stores trading state, secrets, or credentials. It is retrievable only with access filtering and expiry.
5. **Prompt evaluation is required.** Before an agent or prompt is released, it must pass injection, unsupported-claim, refusal, schema, privacy, latency, cost, and regression evaluation suites.

## Alternatives and trade-offs

- **Early AI inclusion (Phase D/E)** — would accelerate research automation but risks the deterministic core being shaped by AI convenience rather than safety evidence. Rejected per EVIDENCE_SYNTHESIS.md ("deterministic capital path first").
- **LLM as risk input** — rejected as non-deterministic and untrusted per AI_AGENT_COMPARISON.md.

## Consequences

- The AI aspects of the handbook (`AI_GOVERNANCE.md`, `RESEARCH_ENGINE.md`) are shelfware until after Phase F. This is intentional and documented.
- Future AI integration will require its own ADRs, tool review, and prompt evaluation.

## Validation and operations

- The AI policy is validated by its absence — no AI code exists in the platform before Phase F.
- Post-Phase F, each AI component requires an ADR, prompt evaluation, and deterministic validator tests.
- Tool denials, schema failures, and unsafe-output rate are monitored from day one of AI enablement.

## Approval

AI Governance Lead — 2026-07-13
