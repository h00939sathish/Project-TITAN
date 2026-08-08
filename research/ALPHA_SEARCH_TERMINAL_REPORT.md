# Project TITAN — Terminal Report (Alpha-Search Phase)

> **Status:** TERMINAL for the alpha-search phase. Per the debated plan's
> P5 condition, honored on evidence (2026-08-08).
> **Owner:** Architecture Council / Research Platform. **Scope:** this
> document closes the *directional/regime/macro signal search on liquid OHLCV*
> and records what the platform is worth going forward. It is not a farewell
> to the project — it is the boundary of one phase.

---

## 1. VERDICT

**No simple directional, regime-gated, or macro-factor signal on liquid OHLCV
data produces enough alpha to survive realistic transaction costs — across
every structural axis and asset class tested.**

This is consistent with efficient-market theory for the most liquid instruments
in the world. It is a *finding*, not a failure of the system.

---

## 2. What was tested (~40 experiments, 6 structural axes, 2 asset classes)

| Axis | Experiments | Verdict | Evidence |
|---|---|---|---|
| Directional single-pair FX (15 concepts) | EXP-00016..25 sweep | **0/15 survive** ≥200 pips/yr × 2 pairs | `screen.py` + EXP-00025 |
| Carry / rate differential | EXP-00023, EXP-00024 | REJECTED — no UIP spot, accrual only | `neg_results/EXP-00023/24` |
| Cross-pair mean-reversion | EXP-00026 | HALTED — not cointegrated (p=0.54) | `EXP-00026_crosspair_mr.md` |
| Vol-clustering as alpha | EXP-00017 + 2-fold retest | **Fails OOS** (IC 0.053/0.038) | `EXP-00017_2fold_retest.json`, ADR-026 |
| Multi-TF confluence (regime gate) | P4 | FAIL — gated degrades 401→356 (bootstrap frac>0 = 0.000) | `P4_multi_tf_confluence_FE.md` |
| Gold macro-momentum (DFII10 + DBC) | P2 | FAIL — 3/4 killed (ann 1.49%, Sharpe 0.31, PF 1.14) | `P2_gold_macro_momentum_FE.md` |

Also: FX momentum/reversal families (EXP-16..22), carry vol variants, spot
gold, and the legacy exploration sweep all recorded in `research/neg_results/`
and `research/results/`.

**Method on ALL series:** frozen kill criteria pre-registered, cost-aware
(spread + slippage + commission), honest OOS (anchored WF or true OOS), no
fabrication, no parameter tweaking post-hoc, promotion gate enforced.

---

## 3. What survived

Nothing. `qualified_variants = frozenset()` for all registered strategies,
and that is the *correct, defensible* end-state of the search phase. The
vol-clustering effect (EXP-00017) — the one promoted candidate — did not
survive its own honest out-of-sample re-test.

---

## 4. What was NOT a failure (the system's actual capabilities)

- **Infrastructure works:** execution engine, HMAC-signed order intents, event
  sourcing, risk gates, IBKR/research adapters — all asset-agnostic, all
  tested (807-test suite green).
- **Governance works:** fail-closed promotion gate correctly blocked every
  unqualified candidate. **It said no 40 times. It was right every time.**
- **Methodology works:** frozen criteria, honest costs, reproducible scripts,
  negative results documented as first-class artifacts.
- **Discipline works:** parked when evidence said park — not when enthusiasm
  ran out.

> The gate's usefulness is not "how many strategies it qualified" (0) — it is
> that it correctly refused to qualify anything. Most retail systems fail by
> promoting a phantom edge; this one failed safely, 40 times.

---

## 5. Untested classes (recorded, not claimed)

- Microstructure / order-flow (OFI) — requires tick data; declined by budget.
- Cross-sectional factor on new instruments (EM FX, rates, cross-asset).
- Anything that does not fit the "OHLCV directional on liquid instruments"
  pattern — e.g. real microstructure, market-making, or capacity-constrained
  niches.

These are the only avenues with (theorized) non-zero alpha, and each needs a
fundamentally *new* evidence source, not more backtests on liquid OHLCV.

---

## 6. What the platform is worth (going forward)

Everything built is **asset-class and signal-class agnostic**:

- Execution (intents → engine → adapters)
- Risk gates, promotion gate, reconciliation
- Frozen-criteria screening engine, cost-aware backtest, WF protocol
- Data pipeline + acquisition scripts (Dukascopy, yfinance, FRED/Treasury)
- The negative-results library — the single most valuable research asset

If a different alpha source is ever identified (one that does not fit the
"OHLCV directional on liquid" pattern), these layers deploy immediately
without change. **The project's durable value is the platform and the honest
negative record — not the (non-existent) alpha.**

---

## 7. Final disposition

- **Alpha search phase: closed** with this document.
- **Platform is not parked** — it remains: a tested, honest, gate-safe
  trading system that correctly refuses to trade until evidence exists.
- **Rollback / resume:** any future search phase must (a) identify a
  hypothesis class NOT already tested here, (b) acquire its data BEFORE the
  backtest, (c) use the frozen-criterion / WF-v2 protocol verbatim, (d)
  register the result in `neg_results/` regardless of outcome.

---

*This is the terminal report of the alpha-search phase. It is the document
the plan's Phase 3 (P5) specifies. It records the structural efficiency of the
tested markets and closes the phase honestly.*