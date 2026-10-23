# TRENDING TRADING PROJECTS — 2026-09-29

Current and recently-emerging GitHub projects, with a hype-vs-substance verdict.
All activity dates verified 2026-09-29 against GitHub releases/commits feeds or REST API.

---

## The three real technical advancements worth watching

1. **NautilusTrader v2 (Rust core rewrite)** — github.com/nautechsystems/nautilus_trader.
   1.231.0 final 1.x (2026-08-02); 2.0.0rc5 (2026-09-15); daily commits. The legacy Cython
   core is being replaced by a Rust+PyO3 runtime — the same architecture TITAN chose. One
   deterministic event-driven core for backtest, paper, and live, with venue
   reconciliation. VERDICT: REAL ADVANCEMENT — this is the reference implementation of
   what TITAN's architecture promises.
2. **databento/dbn + databento-rs** — fixed-width binary market-data format (MBO/MBP/OHLCV-1s),
   dbn v0.70.0 (2026-09-18), commercial backing, Rust live gateway. VERDICT: REAL
   ADVANCEMENT — production data infrastructure, relevant only if TITAN later needs
   tick/L2 (currently no hypothesis justifies the cost).
3. **hftbacktest** — Rust/Python LOB simulation with queue position + latency models,
   rust-v0.9.4 (2025-12-10), used in academic HFT teaching. VERDICT: REAL ADVANCEMENT,
   quieter in 2026 — the reference for fill-fidelity simulation if a microstructure
   hypothesis ever survives TITAN's gates.

## Portfolio/methodology advancements (real, useful later)

4. **skfolio** — portfolio optimization with walk-forward/purged CV designed to avoid
   look-ahead; v1.4.8 (2026-09-28); peer-reviewed (arXiv:2507.04176, 2025-07); ~105k
   PyPI downloads/month. VERDICT: REAL — adopt the CV methodology when TITAN has ≥2
   qualified strategies (currently 0).
5. **Microsoft RD-Agent (with Qlib)** — LLM-driven factor-mining loop with AST guardrails,
   backtest feedback via Qlib; RD-Agent v1.0.0 (2026-09-23), KDD'24 paper; Qlib
   maintenance-active. VERDICT: REAL ADVANCEMENT (research-grade) — the ONE AI-trading
   project with engineering discipline; its loop design (hypothesis → factor → gate →
   feedback) is what TITAN's research loop should be benchmarked against.
6. **RaptorBT** — new Rust/PyO3 vectorized backtester claiming vectorbt metric parity,
   v0.13.4 (2026-09-10), repo created 2026-01, self-tested parity. VERDICT: REAL
   ENGINEERING, UNPROVEN SUCCESSOR — interesting but 47 stars, no independent validation;
   vectorbt itself is alive again (v1.1.1, 2026-09-26).

## The hype layer (popular, weak evidence)

7. **TradingAgents (TauricResearch)** — multi-agent LLM trading framework; v0.5.2
   (2026-09-29); ~109k stars in 21 months; paper claims +23.21%/3mo on 3 hand-picked
   stocks, backtest-only, no broker execution, non-reproducible across LLM runs; authors
   caution against real money. VERDICT: MIXED — real point-in-time backtest hygiene work
   (v0.5.x), hype-level profitability claims. Steal the debate/memory architecture for
   research tooling; reject as a signal source.
8. **ai-hedge-fund** — ~64k stars; README states "educational purposes only… does not
   actually make any trades". VERDICT: HONEST HYPE — pedagogically useful, zero edge
   evidence.
9. **FinRL / FinRL-DeepSeek** — RL trading; v0.3.8 (2026-03-20) adds a tutorial;
   RL-to-live gap remains; no verified post-cost edge. VERDICT: MIXED — established
   research tool, not a trading system.
10. **OpenPilot ("AI quant agent trading live with my own $1000")** — 5 stars, abandoned
    2026-03, claims unverified. VERDICT: HYPE — the canonical example of the category.

## Sector-level conclusions

- The 2024-2026 "new backtesting engine" wave is thin; the credible new entrants are
  Rust-native (NautilusTrader v2, RaptorBT, hftbacktest's Rust line). TITAN's Rust core
  decision is validated by where the ecosystem is going.
- LLM-trading-agent repos are the highest-star, weakest-evidence category. The two
  strongest external audits (arXiv:2605.19337 — 0/19 reproducible studies; AI-Trader live
  benchmark 2026-08 — most agents lose money) say evaluation, not architecture, is the
  bottleneck. TITAN should adopt those reporting checklists, not more agents.
- The strongest verifiable advancement is in execution/microstructure infrastructure
  (NautilusTrader, hftbacktest, roq-api, databento) — none of which TITAN needs until a
  hypothesis justifies it. Trending ≠ needed.
