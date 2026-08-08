# Repository Catalog — Institutional Competitive Gap Analysis

**Date:** 2026-07-17
**Scope:** Competitive Intelligence on 6 Trading Repositories vs Project TITAN

This catalog maps the purpose, architecture, code quality, and testing readiness of all reference platforms against Project TITAN to establish a baseline for competitive feature gap analysis.

## 1. Project TITAN (Candidate)
*   **Purpose:** Target proprietary platform for autonomous research, trading, and execution.
*   **Architecture:** Hybrid Rust/Python event-driven kernel, attempting event sourcing and actor models but currently suffering from "exists but not wired" anti-patterns.
*   **Maintenance:** Active, under heavy architectural audit.
*   **Code Quality:** Good structural intentions, but pre-alpha execution reality (e.g. order state machine not wired).
*   **Testing:** Strong unit tests for some Rust components; completely missing end-to-end integration and recovery tests.
*   **Production Readiness:** Pre-alpha. Blocks on live execution.

## 2. NautilusTrader (Reference - Core Execution)
*   **Purpose:** High-performance, multi-asset event-driven algorithmic trading.
*   **Architecture:** Rust-native core (`crates/execution`) with a Python control plane (`nautilus_trader`). Message Bus, Event Sourced, Actor System.
*   **Maintenance:** Highly active, massive open-source backing.
*   **Code Quality:** Exceptional. Uses `mimalloc`, `tokio`, strict `clippy`, and OpenSSF Scorecard tracking.
*   **Testing:** 12K+ tests, extensive `proptest` fuzzing, property-based boundary testing.
*   **Production Readiness:** **Production Grade**. The gold standard for deterministic simulation and order execution.

## 3. Jesse AI (Reference - Research & Indicators)
*   **Purpose:** Crypto-focused framework for strategy research, optimization, and backtesting.
*   **Architecture:** Python monolithic global state (`jesse.store`), FastAPI backend, Vue frontend. Offloads heavy math to `jesse_rust`.
*   **Maintenance:** Active.
*   **Code Quality:** High developer experience (PEP8), but relies on a God-Object `Strategy.py` class and global state.
*   **Testing:** Thorough test suite covering individual state transitions and strategy regressions.
*   **Production Readiness:** Excellent for research and Optuna/Monte Carlo; weak for multi-asset institutional execution due to global state locks.

## 4. new trade (Reference - Risk & Portfolio)
*   **Purpose:** Event-sourced trading backbone with complex risk gating.
*   **Architecture:** PostgreSQL/TimescaleDB append-only ledger, asyncio python core.
*   **Maintenance:** Abandoned or early stage.
*   **Code Quality:** Mixed. Strong concepts (TimescaleDB, HRP allocator), but catastrophic bugs (blocking pandas in async loop, raw TCP HTTP parsing).
*   **Testing:** Minimal/Weak.
*   **Production Readiness:** Pre-alpha. The deterministic Kill Switch is mathematically sound but implementation (blind market liquidations) is highly dangerous.

## 5. LLM_trader (Reference - AI Advisory)
*   **Purpose:** LLM-integrated market analysis and reasoning engine.
*   **Architecture:** Python-based. Integrates technical indicators with ChromaDB vector memory and a `BrainReflectionEngine` for rule distillation.
*   **Maintenance:** Research stage.
*   **Code Quality:** High conceptually for AI. Demonstrates excellent pattern isolation (falsification prompting, reflection grouping).
*   **Testing:** Research-level.
*   **Production Readiness:** Paper-only. Excellent as an advisory overlay, not an execution engine.

## 6. newFinceptAgentTerminal (Reference - Tooling & Bridge)
*   **Purpose:** Desktop application and Model Context Protocol (MCP) tool registry for autonomous agents.
*   **Architecture:** Hybrid C++/Python. C++ MCP registry bridged via HTTP to Python `finagent_core`.
*   **Maintenance:** Heavy upstream.
*   **Code Quality:** Complex (342K lines C++). Built as a terminal desktop app, not a headless server.
*   **Testing:** Medium. Relies on `dry_run` modes for AI.
*   **Production Readiness:** Desktop-grade, not server-grade. Highly valuable for its MCP schema bridging and FTS5 reflection stores.
