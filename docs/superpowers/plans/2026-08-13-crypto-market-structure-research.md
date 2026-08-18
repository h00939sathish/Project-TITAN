# Crypto Market-Structure Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a research-only, reproducible crypto market-structure screen that can produce a validated candidate or a documented negative result without creating exchange execution authority.

**Architecture:** Ingestion produces immutable venue/source manifests and normalized 24/7 market-structure events. A venue-aware simulator consumes those artifacts and emits cost-attributed, partitioned evidence bundles; it has no dependency on broker adapters or promotion certificates.

**Tech Stack:** Python 3.12, SQLite/object-backed research artifacts, JSON schemas, pytest, existing TITAN research harness.

## Global Constraints

- Do not implement until ADR-029 is Accepted by Architecture Council and Risk Owner.
- No exchange credentials, private API calls, exchange adapters, paper orders, live orders, or promotion certificates.
- Preserve all research inputs, manifests, and negative results; never delete evidence to obtain a pass.
- Start with BTC and ETH only; use point-in-time UTC data and declared venue rules.
- A bar-close constant-bps fill is exploratory only and cannot support promotion or capacity claims.

---

### Task 1: Define crypto contracts and fixtures

**Files:**
- Create: `specifications/CryptoResearch.spec.md`, `contracts/crypto-market-event-v1.schema.json`, `tests/data/fixtures/crypto/`
- Test: `tests/data/test_crypto_contracts.py`

**Interfaces:**
- Produces: `CryptoMarketEvent` JSON with `venue`, `symbol`, `contract_kind`, `occurred_at`, `sequence`, `funding_rate`, `open_interest`, and `source_manifest_digest`.

- [x] Write failing schema tests for a valid UTC perpetual funding event and invalid missing venue, sequence, or manifest digest events.
- [x] Run `python -m pytest tests/data/test_crypto_contracts.py -q`; expect collection failure because the contract and validator do not exist.
- [x] Add the schema, 24/7/UTC and correction rules, BTC/ETH fixtures, and deterministic validation.
- [x] Run the test file; expect all contract tests to pass.

### Task 2: Build read-only ingestion and provenance

**Files:**
- Create: `src/titan/data/crypto.py`, `src/titan/data/calendar_crypto.py`, `research/crypto/manifests/`
- Test: `tests/data/test_crypto_ingestion.py`

**Interfaces:**
- Produces: `ingest_crypto_snapshot(raw_events, manifest) -> list[CryptoMarketEvent]` and `CryptoDataManifest.digest`.

- [x] Write failing tests for checksum mismatch, non-UTC timestamp, duplicate/out-of-order sequence, data gap, and valid 24/7 event retention.
- [x] Run `python -m pytest tests/data/test_crypto_ingestion.py -q`; expect import failure for `titan.data.crypto`.
- [x] Implement only read-only local-file ingestion and manifest validation; do not add exchange credentials or network order capability.
- [x] Run the ingestion tests; expect pass.

### Task 3: Implement venue-aware cost simulation

**Files:**
- Create: `src/titan/backtest/crypto_costs.py`, `src/titan/backtest/crypto_simulator.py`
- Test: `tests/backtest/test_crypto_costs.py`, `tests/backtest/test_crypto_simulator.py`

**Interfaces:**
- Produces: `CryptoCostModel`, `simulate_crypto(events, signal, cost_model, partition) -> CryptoEvidenceArtifact`.

- [x] Write failing tests proving net PnL separately includes bid/ask, maker/taker fee, funding, partial fill, precision/min-notional rejection, and delayed execution.
- [x] Run the two test files; expect import failures for the crypto modules.
- [x] Implement Decimal-based quantity/contract precision and a declared venue cost model. Store data, strategy, parameter, cost-model, and partition digests in every evidence artifact.
- [x] Run both test files; expect pass.

### Task 4: Preregister and execute the three screens

**Files:**
- Create: `research/crypto/hypotheses/CRYPTO-001-funding-basis.md`, `research/crypto/hypotheses/CRYPTO-002-funding-oi.md`, `research/crypto/hypotheses/CRYPTO-003-order-flow.md`, `research/run_crypto_screen.py`
- Test: `tests/research/test_crypto_screen.py`

**Interfaces:**
- Consumes: manifest-validated events and `CryptoCostModel`.
- Produces: `research/crypto/results/CRYPTO-00X-evidence-bundle.json`.

- [x] Write failing tests that reject missing pre-registration fields, reuse of the OOS partition for parameter choice, missing cost attribution, and an unreplicated candidate.
- [x] Run `python -m pytest tests/research/test_crypto_screen.py -q`; expect import failure for `run_crypto_screen`.
- [x] Implement fixed-parameter screens and the charter's gates; write a negative-result artifact whenever a gate fails.
- [x] Run the screen tests on fixture data; expect pass.

### Task 5: Produce research outcome and retain execution denial

**Files:**
- Create: `research/crypto/CRYPTO_DISCOVERY_REPORT.md`
- Modify: `docs/scope/operating-scope.md` only if a future human-approved ADR changes operational scope
- Test: `tests/research/test_crypto_screen.py`

- [x] Write a failing test asserting a crypto research artifact cannot create `TradeIntent`, an adapter, a certificate, or a paper-session configuration.
- [x] Run the test; expect failure until the research package's import boundary is enforced.
- [x] Enforce the research-only package boundary and report gross/net attribution, OOS gates, replication status, and terminal result.
- [x] Run the complete crypto research suite and the pre-existing full suite; record outputs without suppressing tests.

---

## Phase 2: Unblocking CRYPTO-002 and CRYPTO-003

### Task 6: Historical Open Interest (OI) Ingestion & CRYPTO-002 Screen

**Files:**
- Create/Update: `scripts/download_binance_oi.py`, `research/crypto/manifests/binance_oi_v1.json`, `src/titan/research/crypto_screen_002.py`
- Test: `tests/research/test_crypto_screen_002.py`

**Interfaces:**
- Produces: Normalized `OPEN_INTEREST` `CryptoMarketEvent` stream and `CRYPTO-002-evidence-bundle.json`.

- [ ] Build read-only script to fetch/parse historical Open Interest records for BTCUSDT and ETHUSDT.
- [ ] Create and freeze `binance_oi_v1.json` dataset manifest with SHA-256 digests.
- [ ] Implement `funding_oi_deleveraging_signal` according to `CRYPTO-002-funding-oi.md`.
- [ ] Run IS/OOS walk-forward evaluation and output frozen evidence bundle or negative result.

### Task 7: High-Frequency Order-Flow / Trade Ingestion & CRYPTO-003 Screen

**Files:**
- Create/Update: `scripts/download_binance_trades.py`, `research/crypto/manifests/binance_trades_v1.json`, `src/titan/research/crypto_screen_003.py`
- Test: `tests/research/test_crypto_screen_003.py`

**Interfaces:**
- Produces: Sequence-ordered `TRADE` / `QUOTE` `CryptoMarketEvent` stream and `CRYPTO-003-evidence-bundle.json`.

- [ ] Build read-only parser for Binance monthly aggTrades / trade archives with sequence verification.
- [ ] Implement `order_flow_imbalance_signal` per `CRYPTO-003-order-flow.md`.
- [ ] Run evaluation under venue latency and taker fee constraints; emit evidence bundle.

---

## Spec coverage review

Tasks 1-5 cover data provenance, 24/7 semantics, structural hypotheses, venue-specific net costs, independent OOS evidence, terminal negative results, and a strict no-execution boundary. Phase 2 (Tasks 6-7) expands data ingestion to unblock the remaining two preregistered hypotheses. Exchange connectivity, paper trading, and live trading remain deliberately absent and require separate approved scope and broker ADRs.

## Execution Handoff

ADR-029 is accepted (2026-08-14) and Charter is Active. Phase 1 tasks (1-5) are complete. Proceed with Phase 2 Task 6 (CRYPTO-002) using subagent-driven development or inline execution.
