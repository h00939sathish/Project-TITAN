# P2 Pivot — Macro-Momentum on Spot Gold (debated) + VERIFIED CORRECTIONS

> Debated plan: `p2-instrument-choice.md`. State: planned, data-dependent.

## Decided (debated)
- **A1: Instrument = spot gold (XAUUSD).** Highest liquidity, no roll (unlike
  futures), already partially wired (`spot_metal_instrument`, ADR-015). Cost
  pinned at **1.0 bps round-trip**.
- **A2: Signal = Macro-Momentum**, NOT gold-price OHLCV (avoids duplicating the
  failed FX pattern). Drivers:
  - DFII10 (10-yr real yield): `sign(-ΔDFII10_252d)` — falling real yields ⇒
    gold up.
  - DBC (broad commodity index ETF): `sign(Return_DBC_252d)` — rising
    commodities ⇒ gold up.
  - Equal-weight combine. Zero gold-price signal.
- **D: Frozen kill criteria (2007-01..2023-12, WF-v2):** (1) net ann. return
  >4%; (2) OOS Sharpe >0.45; (3) DSR >0.95; (4) profit factor >1.20; (5) max
  OOS DD <20% at 10% vol target. Cost 1.0 bps RT.

### VERIFIED CORRECTIONS (repo ground-truth — pitfall #10)
- **The engine is Python, NOT Rust.** All "`src/core/..._rs.rs`" paths in the
  debate are hallucinated. Real: `src/titan/backtest/fills.py`,
  `src/titan/research/harness.py`, `src/titan/data/spot_metals.py`
  (`spot_metal_instrument`).
- **Cost/sizing models already exist and are parameterized** (`slippage_bps`,
  `commission_bps` in `harness.py`/`fills.py`) — NO rewrite needed; just pass
  1.0 bps total. The debate's "must rewrite cost_model.rs" is wrong.
- **IBKR gold is NOT available** — ADR-015 restricts XAUUSD to sim/backtest
  only; the IBKR adapter for gold is deferred. So the screen runs on historical
  data via the backtest adapter, never a live IBKR path. This matches the
  research-only boundary.
- **Three datasets are NOT in the repo and must be acquired first:**
  - `DFII10` real yields — FRED (need ALFRED PIT vintage or a factually locked
    T+lag; currently absent — fred/ has DFF, ECBDFF, FX rates only).
  - `DBC` (Invesco DB Commodity Index ETF) daily — via yfinance (used elsewhere
    in repo: `fetch_real_data.py`, `run_intraday_research_backtests.py`).
  - Real XAU daily history (only a 7-line smoke fixture `xauusd_2026.csv`
    exists). Sources: yfinance `XAUUSD=X`, or the free Dukascopy/BI5 puller.

### Sequencing (data-first)
1. Acquire DFII10 (FRED), DBC (yfinance), XAU daily (yfinance/XAUUSD=X) —
   a debated, evidence-led download; FREe tier, no cost.
2. Validate alignment (dates, no gaps) against the 2007-2023 window needed for
   full regime coverage (GFC/ZIRP/2022).
3. Implement the macro-momentum screen in Python (reuse harness.py cost model).
4. Run WF-v2, pipe to kill-criteria engine, honest PASS/FAIL.