# CLAUDE.md

This file provides guidance to C‍laude Code (claude.ai/code) when working with code in this repository.

## Build and Execute
- **Python Setup**: Uses `uv` and `maturin`. (`uv run` or standard `pip`/`pytest` depending on environment).
- **Run Python tests**: `python -m pytest tests/ -v -p no:cacheprovider` or `pytest tests/` (Run single test with `pytest tests/path/to/test.py::test_name`).
- **Typing & Linting (Python)**: `mypy src/titan tests/` and `ruff check src/`
- **Build Rust core (Maturin)**: `maturin build --release --manifest-path core/Cargo.toml`
- **Run Rust tests**: `cargo test --manifest-path core/Cargo.toml`
- **Run Rust linter**: `cargo clippy --manifest-path core/Cargo.toml -- -D warnings`

## Architecture Overview
Project TITAN is an autonomous quantitative research and trading OS divided into distinct modules, separated into a Python layer (`src/titan`) and a high-performance, deterministic Rust core (`core/Cargo.toml` compiled into `_core`).

### Boundaries and Key Invariants 
- **Deterministic Risk Pipeline**: AI proposes, deterministic systems decide. A Strategy emits a `TradeIntent` to the Risk gate, which alone has authority to emit an `ApprovedOrderIntent` and send it to Execution. No AI delegates or executes orders.
- **Fail-Closed & Strong Typing**: Avoid catch-and-ignore. Treat external data as untrusted (validate schemas/limits/hashes). Uses strictly typed messages (`MarketEvent`, `TradeIntent`, `RiskDecision`).
- **Core Rust Engine**: Domain messages, state machines (Order, Portfolio), and risk engines (limits, state, kill-switches) are implemented in Rust. State transitions are event-driven and append-only.
- **Python Ecosystem**: 
  - `titan.execution`: Adapters (IBKR, Alpaca, Simulated), manages order submit, timeouts, reconcile.
  - `titan.risk`: Python wrappers around the Rust RiskGate pipeline.
  - `titan.research / titan.backtest`: Offline discovery tools. In-sample validations, generating absorbing negative results, pre-registration artifacts, point-in-time cross-sectional equities/crypto/fx factor logic.
- **Data & Configuration**: Explicit point-in-time cost models (`FxCostModel`) and promotion gates (cryptographic `PromotionCertificate`). 

## Governance & Standard
- **ADR Gateline**: Production code changes in `core/` or `src/titan/` (excluding tests) require an accepted Architecture Decision Record (ADR) under `docs/adr/`. Enforced via pre-commit.
- **Evidence-Led**: Testing layers start at Unit (Rust bounds) and go through Simulation (Cost Frictions) and Chaos. Never claim an undocumented consequence. All behavior modifications must be tested (Recovery/Replay).
