# CURRENT GITHUB COMPETITIVE MATRIX — 2026-09-29

TITAN vs the strongest currently-relevant open projects. Activity evidence verified
2026-09-29 via GitHub REST API, releases.atom / commits.atom feeds, and PyPI JSON.
Star counts are included only as context, never as evidence of quality.
TITAN column = implementation status, NOT documentation status.

Legend for TITAN STATUS: YES (working) / PARTIAL / BROKEN / DOC-ONLY / NONE

| Dimension | TITAN STATUS | Reference capability | Evidence (reference) | GAP | Relevance |
|---|---|---|---|---|---|
| Market data | PARTIAL | NautilusTrader: 100+ adapters, nanosecond data model; databento/dbn: fixed-width binary format | nautilus 1.231.0 (2026-08-02), daily commits; dbn v0.70.0 (2026-09-18) | TITAN has 3 live feeds + 1y midpoint FX; no tick/L2, no multi-year intraday | HIGH — data blocks TITAN's next research class |
| Research (factors) | PARTIAL | Qlib v0.9.7: Alpha158/360, point-in-time handlers, rolling retrain; zipline-reloaded Pipeline API | qlib commits to 2026-09-22; zipline-reloaded 3.1.1 (2025-07-19) | TITAN has no cross-sectional factor engine; equity research used small universes | HIGH |
| Backtesting | PARTIAL (2 divergent engines; engine path broken) | NautilusTrader: ONE deterministic event core for backtest AND live; vectorbt v1.1.1 (2026-09-26) + Rust engine for sweeps | nautilus v2.0.0rc5 (2026-09-15) Rust+PyO3 rewrite | TITAN's harness≠engine; ReplayEngine crashes at cert gate; same-bar fills | CRITICAL — this is TITAN's own stated architecture, unimplemented |
| Replay | PARTIAL | NautilusTrader replay; trade-executor deterministic decision replay (v1462, 2026-09-28) | | TITAN event store is append-only + dedup, but fill-delta restore bug (B4) breaks restart correctness | HIGH |
| WFO | YES (basic) | vectorbt.pro "portfolio continuation"; skfolio walk-forward CV (v1.4.8, 2026-09-28) | | TITAN has walkforward.py but freeze unenforced; no portfolio-level WFO | MED |
| Monte Carlo | DOC-ONLY | vectorbt bootstrapping; HftBacktest | | no code in TITAN | MED |
| Optimization | PARTIAL (grid only) | jesse Optuna/DNA (v3.2.3, 2026-09-27); freqtrade hyperopt (2026.8, 2026-08-31) | | grid sweeps with best-IS selection + OOS leak | MED — overfitting risk |
| Strategy framework | YES (registry+lifecycle) | NautilusTrader actor model; bt strategy stacking (v1.2.4, 2026-09-17) | | TITAN lifecycle machine never had an ACTIVE strategy pass through it | LOW |
| Portfolio construction | PARTIAL (dead HRP allocator) | PyPortfolioOpt 1.6.0 (2026-02-26); skfolio (peer-reviewed, arXiv:2507.04176) | | nothing qualified → nothing to combine; no vol targeting (pysystemtrade) | MED — needed only after ≥2 qualified |
| Risk | YES (Rust, tested) | Lean Algorithm Framework risk modules; NautilusTrader risk engine | lean daily tags (18136, 2026-09-28) | TITAN is genuinely competitive here; missing net/sector/vol limits | LOW — preserve |
| Execution | PARTIAL (engine real, admission broken) | NautilusTrader live exec + reconciliation; roq-api C++20 gateways (v1.1.8, 2026-08-07); HftBacktest LOB/queue/latency sim (rust-v0.9.4, 2025-12-10) | | no LOB fill model; no live broker economics recording; cert seam unbuilt | HIGH — the broken seam |
| Broker integration | PARTIAL (IBKR paper-locked, Alpaca, Fincept dead) | lumibot ~12 brokers (v4.6.2, 2026-09-27); hummingbot connector fleet (v2.17.0, 2026-09-22); NautilusTrader 20+ | | breadth not the issue; economics measurement is | LOW-MED |
| Reconciliation | YES (Rust, thresholds, kill-switch) | NautilusTrader venue reconciliation | | competitive; cash self-comparison fallback (L4) | LOW — preserve |
| Observability | PARTIAL (prometheus dump; documented metrics don't exist) | freqtrade telegram/web UI; NautilusTrader logs/telemetry | | MTF metrics documented but absent from registry | MED |
| Recovery | YES (fail-closed, tested) | NautilusTrader fault tolerance | | competitive; restart bugs B4/B5 live in untested paths | LOW |
| Paper trading | BROKEN | freqtrade dry-run; NautilusTrader paper venues | | cert gate + no session init + no cost model | CRITICAL |
| AI | DOC-ONLY (advisory) | Qlib+RD-Agent factor-mining loop (RD-Agent v1.0.0, 2026-09-23); TradingAgents v0.5.2 (2026-09-29) debate architecture | | external evidence: NO public LLM trading system has verified profitability (AI-Trader 2026-08; 2605.19337) | MED — adopt eval checklists only |
| Agent architecture | NONE | TradingAgents roles/debate/memory; RD-Agent KDD'24 loop | | | LOW |
| Memory | DEAD (imported by nothing) | FinMem layered memory (dormant 2024-08) | | | LOW |
| Tool use | NONE | the0 MCP bot executor (2026-09-28) | | | LOW |
| Performance | GOOD (Rust core) | NautilusTrader Rust v2; RaptorBT sub-ms (v0.13.4, 2026-09-10) | | TITAN fine at its scale | LOW |
| Testing | MASKED (1180 green, prod crashes) | NautilusTrader extensive pytest + Rust tests | | conftest monkeypatch; vertical slice bypasses submit_intent | CRITICAL |
| Deployment | NONE (Windows-hardcoded ops scripts; no CI gate proven) | freqtrade docker; hummingbot docker | | ADR-034 repointed a dead workflow; mypy advisory | MED |
| Developer experience | MIXED (strong docs/ADRs, but docs outrun code) | jesse docs; NautilusTrader docs | | runbook claims don't match behavior | MED |

## Verdicts per dimension class

- **TITAN is genuinely competitive**: risk core, reconciliation, event store, recovery
  discipline, honest negative-result research record. No open project in this matrix has a
  more rigorous promotion-gate philosophy; most have none.
- **TITAN is behind where its own architecture promised**: single-engine backtest/live
  parity (NautilusTrader has it, TITAN documents it), point-in-time cross-sectional
  research (Qlib), and a working paper loop (freqtrade's dry-run is trivial by comparison
  but WORKS).
- **Nothing in the ecosystem invalidates TITAN's Rust+Python choice** — NautilusTrader v2
  is converging on the same architecture. The gap is integration and honesty of
  verification, not design.
- **The two patterns worth stealing**: (1) NautilusTrader's one deterministic core across
  backtest/paper/live with venue reconciliation — TITAN already owns 80% of this in Rust
  and should finish the wiring rather than adopt a new framework; (2) HftBacktest-style
  LOB/queue simulation — only if a microstructure hypothesis survives on real data.
