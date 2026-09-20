# Project TITAN

> **Status:** ARCHIVED — alpha search concluded (2026-08-08). Platform preserved.
> **Phase terminal report:** [research/ALPHA_SEARCH_TERMINAL_REPORT.md](research/ALPHA_SEARCH_TERMINAL_REPORT.md)
> **Retrospective:** [RETROSPECTIVE.md](RETROSPECTIVE.md)
> **Governance:** [AGENTS.md](AGENTS.md) (constitution), [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md)

## What TITAN is (was)

An institutional-grade autonomous quantitative research and trading operating
system: AI-assisted research proposing structured hypotheses, deterministic
validation, typed strategy intents, a fail-closed risk and promotion gate, and
a reconciled paper/live execution path. Built as a governed synthesis of R&D
evidence — not a copy of any evaluated repository.

## What it accomplished

- **A production-grade, instrument-agnostic platform:** execution engine,
  HMAC-signed order intents, event-sourced state, risk gates, promotion
  pipeline, IBKR paper adapter, cost-aware screening engine, pre-frozen
  walk-forward protocol.
- **An honest evaluation methodology:** every hypothesis tested with
  pre-registered kill criteria, realistic costs, and reproducible scripts.
- **A negative-results library:** ~40 experiments across 6 structural axes and
  2 asset classes (FX majors, spot gold), 0 survivors, each result documented
  in `research/neg_results/` with evidence on file. The post-pivot programs
  (crypto market structure ADR-029, equities cross-sectional factors ADR-030)
  added 13 more pre-registered hypotheses (CRYPTO-001..004, EQ-001..008,
  EQ-Micro-001, FX-001/002) — likewise 0 survivors; evidence in
  `research/crypto/results/` and `research/equities/results/`. CRYPTO-005
  (passive spread capture) was rejected earlier, at its IS-month feasibility
  probe, and never reached an OOS read (a probe-gated, not absorbing, outcome).

## Current status

**The alpha-search phase is closed by evidence, not by exhaustion of effort.**
No simple directional, regime-gated, or macro-factor signal on liquid OHLCV
data cleared realistic transaction costs. The promotion gate said "no" ~40
times and was correct every time — no strategy was ever promoted without
evidence, and no bad trade was ever placed.

The platform itself remains intact, tested, and asset-agnostic. If a
fundamentally different alpha source is ever identified — one outside the
"OHLCV directional on liquid instruments" pattern — the execution, risk,
governance, and screening layers deploy without change.

## Repository map (post-archive)

```
research/
  neg_results/            # the negative-results library (most valuable asset)
  ALPHA_SEARCH_TERMINAL_REPORT.md
  results/                # frozen experiment evidence
  gold_assets/ fred/      # acquired research data (small, tracked)
docs/
  reference/              # reference documentation (moved from root)
  adr/                    # 22 decision records
  archive/                # superseded tracked plans (PLAN, ROADMAP)
Root: 9 governance docs (AGENTS, OPERATING_PRINCIPLES, PROJECT_TITAN, ...)
```

## How to run the test suite

```bash
python -m pytest tests/ -v -p no:cacheprovider
```

807 tests across strategy, research, data, backtest, replay, recovery, and
adapter suites. Note: pytest resolves `titan` from the installed wheel
(site-packages), so sync changed modules there before running
(`cp src/titan/... <site-packages>/titan/...`).

## License / ownership

Proprietary. Owner and decision authority: Architecture Council and Risk
Owner. See AGENTS.md.