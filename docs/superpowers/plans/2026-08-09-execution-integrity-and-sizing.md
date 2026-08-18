# Execution Integrity and Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent all uncertified execution, keep shadow activity outside adapters, and make research/runtime sizing and promotion evidence identical in semantics.

**Architecture:** A signed, content-addressed promotion certificate is the sole runtime eligibility artifact. A shadow ledger handles candidate proposals without constructing executable intents. Research and runtime use one deterministic sizing and cost-aware evidence model.

**Tech Stack:** Python 3.12, Rust/PyO3 message contracts, SQLite, canonical JSON, Ed25519 verification, pytest.

## Global Constraints

- Do not implement until ADR-028 is Accepted by Architecture Council and Risk Owner.
- Preserve the negative-results library and legacy qualification metrics; never delete evidence.
- Empty certificate registry means no adapter-bound execution.
- Test each changed behavior red-green before implementation; do not disable or delete tests.
- Use one pinned, reproducible Python 3.12 environment and compiled extension.

---

### Task 1: Approve contracts and document admission

**Files:**
- Modify: `specifications/Execution.spec.md`, `specifications/TradeIntent.spec.md`, `specifications/StrategyRuntime.spec.md`, `specifications/Risk.spec.md`
- Test: `tests/test_execution_integrity.py`

**Interfaces:**
- Produces: `ExecutionCertificateRef(certificate_id: str, content_digest: str)` carried by executable intents.

- [ ] Write a failing contract test asserting `PaperTradingEngine.submit_intent` rejects an intent with no certificate reference.
- [ ] Run `python -m pytest tests/test_execution_integrity.py::test_engine_rejects_intent_without_certificate -q`; expect failure because admission is not implemented.
- [ ] After ADR-028 acceptance, extend the four specifications with certificate validation before risk/order routing, shadow-only proposal behavior, rejection reason codes, sizing errors, metrics, and rollback.
- [ ] Run the contract test again after Task 4; expect pass.

### Task 2: Implement certificates and legacy retirement

**Files:**
- Create: `src/titan/research/promotion_certificate.py`, `scripts/migrations/migrate_legacy_qualifications.py`
- Modify: `src/titan/research/db.py`, `pyproject.toml`
- Test: `tests/test_execution_integrity.py`

**Interfaces:**
- Produces: `PromotionCertificateRegistry.verify(intent) -> CertificateValidation` and `migrate(db_path, apply=False) -> MigrationResult`.

- [ ] Write failing tests for valid signed certificate acceptance; forged, expired, revoked, and digest-mismatched rejection; plus migration dry-run/commit/idempotence/audit retention.
- [ ] Run those tests; expect import failures because certificate and migration modules do not exist.
- [ ] Implement canonical JSON serialization, SHA-256 digest calculation, Ed25519 verification, strict certificate field matching, and an append-only `qualification_status_events` table. Implement transactional migration with verified-path backup and `--apply` as the only mutating mode.
- [ ] Run certificate and migration tests; expect pass.

### Task 3: Implement canonical sizing

**Files:**
- Create: `src/titan/strategies/sizing.py`
- Modify: `src/titan/research/harness.py`, `src/titan/strategies/multitimeframe_runtime.py`
- Test: `tests/test_execution_integrity.py`

**Interfaces:**
- Produces: `Sizer.size(equity, allocation_pct, price, conversion_rate, conversion_timestamp, step_size, minimum_quantity, now) -> SizingResult`.

- [ ] Write failing tests for research/runtime parity, step-size floor, insufficient allocation, missing conversion, and stale conversion.
- [ ] Run sizing tests; expect import failure for `Sizer`.
- [ ] Implement the pure decimal `Sizer`; remove `buy_qty=10`, `DEFAULT_EQUITY`, and `max(1, ...)` sizing paths. Backtest receives the same immutable equity/conversion snapshot used by runtime.
- [ ] Run sizing tests and affected research/runtime tests; expect pass.

### Task 4: Enforce layered shadow and execution admission

**Files:**
- Modify: `scripts/ibkr_paper_session.py`, `src/titan/execution/engine.py`, `src/titan/runtime/events.py`, relevant Rust/PyO3 `TradeIntent` contract files
- Test: `tests/test_execution_integrity.py`, `tests/adapters/test_paper_session_admission.py`

**Interfaces:**
- Consumes: `PromotionCertificateRegistry`, `ExecutionCertificateRef`, `SizingResult`.
- Produces: adapter submission only after certificate validation.

- [ ] Write failing tests proving a shadow proposal writes ledger evidence and invokes no adapter, and proving an uncertified intent is rejected even when submitted directly to the engine.
- [ ] Run those tests; expect failure because shadow proposals currently call `submit_intent`.
- [ ] Implement a separate shadow ledger/simulator branch before intent construction; increment shadow metrics there. Add engine-side certificate verification immediately before risk/order admission and return typed rejection reasons.
- [ ] Run the new tests, then the affected adapter/runtime suites; expect pass.

### Task 5: Replace promotion evidence and make builds reproducible

**Files:**
- Modify: `src/titan/research/promotion.py`, `README.md`, `pyproject.toml`, lockfile/toolchain configuration
- Test: `tests/test_execution_integrity.py`, existing promotion tests

- [ ] Write failing tests that reject cost-free return artifacts and accept only persisted simulator evidence whose metadata has all required digests and IS/OOS boundaries.
- [ ] Run the tests; expect failure because `_strategy_return_series` is currently admitted.
- [ ] Replace derived series use with a typed persisted cost-aware evidence artifact. Pin exact runtime/test/build dependencies and Python 3.12; update README to use `pip install -e .` or `maturin develop` only.
- [ ] Create a fresh virtual environment, install/build, and run `python -m pytest -q`; record exact output and resolve all collection failures without deleting tests.

### Task 6: Operate and verify

**Files:**
- Modify: metrics/logging modules and relevant runbook/spec sections
- Test: `tests/test_execution_integrity.py`

- [ ] Write failing tests for shadow metrics and `shadow_adapter_submission_total == 0`.
- [ ] Run metric tests; expect failure before metrics exist.
- [ ] Implement the five ADR-028 metrics and structured rejection/audit logging; document alert thresholds and rollback procedure.
- [ ] Run full test suite, clean build, migration dry-run, migration apply against a disposable DB, and a paper-data session with only shadow candidates. Verify no adapter submission and preserve outputs as acceptance evidence.

## Spec coverage review

Tasks 1-6 cover every v3 requirement: governance/specification changes, append-only legacy retirement, shared safe sizing, two-layer shadow/admission isolation, signed provenance, persisted cost-aware evidence, reproducible builds, and all listed acceptance tests. The plan adds Rust contract work because certificate provenance cannot be checked at the engine boundary if the intent cannot carry it.

## Execution Handoff

ADR-028 is drafted at `docs/adr/ADR-028-execution-integrity-and-sizing.md`. After Architecture Council and Risk Owner acceptance, execute this plan inline in this task unless the user asks for delegated execution.
