# AI Governance

> **Owner:** AI Governance Lead
> **Status:** Active — v1.1
> **Last Review:** 2026-08-18
> **Decision Authority:** AI Governance Lead and Risk Owner
> **Depends On:** [AGENTS.md](AGENTS.md), [specifications/Execution.spec.md](specifications/Execution.spec.md), [specifications/Risk.spec.md](specifications/Risk.spec.md), [specifications/TradeIntent.spec.md](specifications/TradeIntent.spec.md), [RISK_POLICY.md](RISK_POLICY.md)
> **Supersedes:** v1.0
> **Review Frequency:** Per model/tool/prompt change; monthly otherwise

## Authority boundary

AI is an advisory capability for research, retrieval, hypothesis generation, structured extraction, falsification, documentation, and post-trade reflection. It never holds broker credentials, signs orders, changes portfolio/balance state, approves execution, evaluates hard risk limits, releases a halt, issues promotion certificates (`PromotionCertificate`), or modifies production configuration. The boundary responds directly to the LLM-risk and prompt/security concerns in `../AI_AGENT_COMPARISON.md`, `../FAILURE_ANALYSIS.md`, and ADR-028.

## Permissions and tools

Agents receive explicit allow-listed tools, least-privilege identity, time/usage budget, input/output schema, and audit trail. Tools are classified: **read-only research** may access approved public or licensed sources; **write-draft** may create reviewable artifacts outside production authority; **controlled analysis** may query redacted datasets; **forbidden** includes broker/order/risk/portfolio mutators, certificate issuers, secret stores, shell/network escape, and production deployment. Tool calls are validated by a deterministic policy layer, not by prompt instruction.

## Prompt and memory lifecycle

Prompts are versioned artifacts with purpose, owner, allowed tools, model/provider, evaluation set, safety instructions, and rollback version. Inputs are classified, minimized, injection-scanned, and redacted before provider submission; outputs are schema-validated and provenance-tagged. Vector memory stores source pointer, content hash, embedding model/version, access class, expiry, and deletion status. It is advisory and may be retrieved only with access filtering; it cannot retain secrets, become operational state, or outlive source-retention rights.

## Hallucination, confidence, and override policy

Every consequential output identifies sources, uncertainty, and known gaps. Confidence is a calibrated communication label, never a trading/risk input. Deterministic validators override model output on schema, policy, factual-source, numeric, permission, and safety failure. When evidence is insufficient or tools fail, the safe result is `unknown`/abstain and escalation—not invention, retry loops without bound, or a degraded execution path.

## Reflection and communication

Reflection consumes completed, redacted, immutable research and trade facts to propose hypotheses, tests, or documentation updates. It cannot write back to strategies, limits, or live configuration. Agents communicate through typed work items: `ResearchQuestion`, `EvidenceClaim`, `Hypothesis`, `FalsificationRequest`, `ReviewFinding`, and `Proposal`, each with author/model/prompt version, source ids, confidence label, and expiry. A human or deterministic workflow promotes a proposal through the gates in `specifications/Replay.spec.md`, `docs/adr/ADR-028-execution-integrity-and-sizing.md`, and `RISK_POLICY.md`.

## Evaluation and incident handling

Before release, evaluate prompt/model/tool changes against injection, unsupported-claim, refusal, schema, privacy, latency, cost, and regression suites. Monitor tool denials, schema failures, unsafe-output rate, source coverage, cost, and provider failure. Suspend an agent on unauthorized tool attempts, secret exposure, policy bypass, or unexplained behavior; preserve minimum necessary audit evidence, rotate affected credentials, and investigate.


