# Project TITAN

> **Status:** ACTIVE — platform in use, research programs continuing.
> **Alpha search on liquid OHLCV closed 2026-08-08 by evidence** (0 survivors); the platform was preserved, not abandoned. See [research/ALPHA_SEARCH_TERMINAL_REPORT.md](research/ALPHA_SEARCH_TERMINAL_REPORT.md).
> **Now:** post-pivot programs — crypto market structure (ADR-029) and equities cross-sectional factors (ADR-030). In flight: CRYPTO-006/007 maker-capture and rebate-regime hypotheses.
> **Retrospective:** [RETROSPECTIVE.md](RETROSPECTIVE.md)
> **Governance:** [AGENTS.md](AGENTS.md) (constitution), [OPERATING_PRINCIPLES.md](OPERATING_PRINCIPLES.md)

## What TITAN is (was)

An institutional-grade autonomous quantitative research and trading operating
system: AI-assisted research proposing structured hypotheses, deterministic
validation, typed strategy intents, a fail-closed risk and promotion gate, and
a reconciled paper/live execution path. Built as a governed synthesis of R&D
evidence — not a copy of any evaluated repository.

## What TITAN accomplished

- **A production-grade, instrument-agnostic platform:** execution engine,
  HMAC-signed order intents, event-sourced state, risk gates, promotion
  pipeline, IBKR paper adapter, cost-aware screening engine, pre-frozen
  walk-forward protocol.
- **An honest evaluation methodology:** every hypothesis tested with
  pre-registered kill criteria, realistic costs, and reproducible scripts.
- **A negative-results library:** the 2026-07/08 directional program on liquid
  OHLCV closed with 0 survivors — every one documented in
  `research/neg_results/` with evidence on file. The post-pivot programs
  (crypto market structure ADR-029, equities cross-sectional factors ADR-030)
  added 13 more pre-registered hypotheses (CRYPTO-001..005, EQ-001..008,
  EQ-Micro-001, FX-001/002) — likewise 0 survivors; evidence in
  `research/crypto/results/` and `research/equities/results/`. CRYPTO-005
  (passive spread capture) was rejected earlier, at its IS-month feasibility
  probe, and never reached an OOS read (a probe-gated, not absorbing, outcome).

## Current status

**The directional alpha search is closed by evidence, not by exhaustion of
effort.** No simple directional, regime-gated, or macro-factor signal on liquid
OHLCV data cleared realistic transaction costs. The promotion gate said "no"
repeatedly and was correct every time — no strategy was ever promoted without
evidence, and no bad trade was ever placed.

The platform remains intact, tested, and asset-agnostic, and the search continues
under the post-pivot charters in `docs/adr/ADR-029` and `docs/adr/ADR-030`.
Per-hypothesis outcomes — including pre-registration, kill criteria, and the
absorbing-negative-result rule — are the authoritative record, not this file.

## Repository map

```
research/
  neg_results/            # the negative-results library (most valuable asset)
  ALPHA_SEARCH_TERMINAL_REPORT.md
  CROSS_MARKET_ALPHA_CHARTER.md
  results/                # frozen experiment evidence
  crypto/ equities/       # post-pivot programs (ADR-029, ADR-030)
  gold_assets/ fred/      # acquired research data (small, tracked)
docs/
  reference/              # reference documentation
  adr/                    # 29 decision records
  archive/                # superseded tracked plans (PLAN, ROADMAP)
  scope/ runbooks/        # threat model, capital policy, operational runbooks
specifications/           # subsystem specs + the six-condition implementation gate
Root: 13 governance and standards docs (AGENTS, OPERATING_PRINCIPLES, ...)
```

## How to run the test suite

```bash
.venv/bin/python -m pytest tests/ -v -p no:cacheprovider
```

1196 tests collected across strategy, research, data, backtest, replay,
recovery, and adapter suites. `titan` is installed into `.venv` as an editable
path install (`titan.pth`), so source edits under `src/titan/` take effect with
no sync step.

## License / ownership

Proprietary. Owner and decision authority: Architecture Council and Risk
Owner. See AGENTS.md.