# EXECUTION ECONOMICS — 2026-09-29

Question: is execution strong enough to preserve whatever edge research finds?
Answer: TITAN has spent its effort protecting execution ADMISSION (certificates, risk
gates, reconciliation) while barely measuring execution ECONOMICS (what fills and fees
actually do to strategy PnL). The asymmetry is now structural.

---

## 1. Signal edge vs transaction cost vs execution drag — the measured numbers

| Strategy / effect | Gross | Costs | Net | Verdict |
|---|---|---|---|---|
| G10 XS momentum 1m/wk (EXP-00022) | +0.10%/period (t=2.67) | 10 bps/leg | **0.00%** | costs consume the entire effect |
| EURUSD short-rally (EXP-00019) | +2.73 pips top-bottom | real spread | +0.58 pips/day; +1.95 (12-16 UTC) | marginal survival |
| Same, rolling (EXP-00020) | +6.25 pips/trade (in-sample) | real engine | **-20.00 pips/trade** (V2, 610 rejects) | execution destroys it |
| FX intraday momentum (EXP-00016) | IC -0.083 (already negative) | 10 bps | — | no gross edge at all |
| FX carry (EXP-00023) | +0.18%/mo (t=1.14) | 10 bps | statistically insignificant | weak gross, weak net |
| Crypto spread capture (CRYPTO-005) | half-spread ~0.05 bps | 2 bps maker fee (40×) | **-2.02 to -2.04 bps/fill** | fee wall |
| traderdev F1 4h (EXP-00025) | — | real spread + 0.5bps slip + 0.2bps comm | +71.8 / +336.5 pips per 12mo | the only positive net result in the entire project |

TITAN's own FX conclusion: expected per-trade edge 0-2 pips vs spread 0.6+ pips and $2.00
commission floor per side (WHY_OUR_FOREX_SYSTEM_IS_NOT_CREATING_ALPHA.md:7).

**Pattern**: in every case the gross effect is small (0-3 pips or 0.1%/period) and the
cost layer is comparable in size. Execution economics IS the ballgame at these edges —
and it is precisely the layer TITAN measures least.

## 2. What the execution layer actually models today

| Layer | Backtest harness | ReplayEngine | Paper engine |
|---|---|---|---|
| Spread | FxCostModel half-spread (assumed 0.10/0.50 bps, fx_costs.py:64-77) | 0 by default (engine.py:81-82) | **none** |
| Commission | 1.0 bps legacy / 0.20 bps + $2 min FX | 0.0 default | **none — fees hardcoded Money("0"), engine.py:736** |
| Slippage | 0.5 bps legacy / 0.10 bps FX | 0.0 default | **none** (fills at intent price) |
| Fill timing | next-bar (harness.py:98) — correct | **same-bar close (engine.py:294→306)** — optimistic | immediate at limit |
| Partial fills / rejects | none | none | supported (sim adapter) |
| Latency | none | none | none |
| Financing | swap -0.15 bps/day assumed (fx_costs.py:52-54) | none | none |

Four divergent cost semantics coexist; scripts disagree with each other (slippage 0.10 to
1.0 bps across qualification_pipeline.py:429-430, run_fx002_asian_expansion.py:45,
backtest_per_timeframe.py:69-141). There is no canonical sweep; the ADR-031 adverse variant
(0.50/0.50/0.50 bps, fx_costs.py:73-95) is **used only in tests**.

## 3. The damaging asymmetries

1. **Research is cost-aware, runtime is cost-free.** Promotion evidence pays 0.2 bps + $2
   min + spread; paper fills pay nothing. Any strategy that looks worse in research than
   in paper will appear to "improve" once running — paper results will systematically
   overstate. This asymmetry is the inverse of ADR-028:5's intent.
2. **The engine path (ReplayEngine) that produces "canonical" candidate evidence
   (replay_traderdev_ema9vwap.py, run_exp20_strategy.py) defaults to zero costs and
   same-bar fills.** EXP-00020 is the direct proof of the damage: in-sample +6.25
   pips/trade, real-engine -20.00 pips/trade.
3. **No broker-side economics exist at all**: no fill audit vs. quoted spread, no
   reject/partial-fill statistics from IBKR/Alpaca paper, no measured slippage. The only
   broker evidence in the whole project is one 1-share SPY round trip
   (knowledge/certifications/one-order-paper-execution-2026-07-14.md).
4. **Adverse-cost scenarios are never run in research** (with_adverse_costs is test-only) —
   so no strategy has been stress-tested at 0.5/0.5/0.5 bps. Given every surviving gross
   edge is 0-3 pips, this is the single cheapest robustness test available and it has not
   been done.

## 4. Is execution strong enough to preserve edge?

- **Admission/integrity machinery**: yes — over-built even (certificates, risk tokens,
  dual-approval release, reconciliation-gated kill switch). Correct and tested.
- **Economics measurement**: no — nearly absent. TITAN cannot currently answer "what do
  fills actually cost on our broker?" with data.

## 5. What to do (economics-first, minimal)

1. Make paper-engine fills pay the SAME cost model as promotion evidence (spread +
   commission + min-fee floor). One config object, shared.
2. Delete the zero-cost ReplayEngine defaults; route all canonical evidence through the
   harness (next-bar) or fix ReplayEngine fill timing.
3. Run every surviving candidate through the existing adverse variant (0.5/0.5/0.5 bps)
   before any gate decision. Zero new code.
4. Add a fill-economics recorder to the paper engine (quoted spread at intent time vs
   fill price, per-fill commission) — this is the ONLY way to replace assumed spreads
   (fx_costs.py defaults) with measured ones, and it requires paper mode to actually run
   (see Runtime Map: it currently cannot).
