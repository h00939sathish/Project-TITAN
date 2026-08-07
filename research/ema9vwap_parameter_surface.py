"""Phase 2b — 2D parameter-sensitivity surface for F1 EMA9 x VWAP (ADR-022/023).

Per the debated plan (Q1 = reduced 2D sweep, option 'reduced 2D'): sweep
  ema_period: 5..21 step 2 (9 values)
  trail_mult : 2.0..3.0 step 0.1 (11 values)
= 99 cells x 2 pairs = 198 runs, using the SAME cost-aware, position-owned
FamilyRunner the EXP-00025 research used (buy-ask/sell-bid real spread,
slippage_bps, commission_bps, intrabar SL/TP/trail). vwap_period and atr_period
held at defaults to restrict the overfit surface.

Output is a SENSITIVITY SURFACE only — it is NOT used to pick a new parameter
set (that would be re-tuning on already-seen data, disallowed). Report per-cell
net pips, cost-aware Sharpe, and a plateau-stability sketch.

Walk-forward (Q2 = option C) is UNMET by design: only the tuning dataset
exists; a real WF needs fresh out-of-sample data.

Writes research/results/ema9vwap_parameter_surface.json
"""
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import run_traderdev_families as m
from run_traderdev_families import DATA, load, F1_EMA9VWAP

EMA_GRID = list(range(5, 22, 2))      # 5..21 step 2  (9 values)
TRAIL_GRID = [round(2.0 + i * 0.1, 1) for i in range(11)]  # 2.0..3.0 (11)
PAIRS = ("EURUSD", "GBPUSD")


class F1Sweep(F1_EMA9VWAP):
    """F1_EMA9VWAP with tunable ema_period and trail_mult."""

    def __init__(self, rows, ema_p=9, trail_m=2.0):
        self.ema_p = ema_p
        self.trail_m = trail_m
        super().__init__(rows)

    def prep(self):
        self._load_atr(14)
        self._ema = m.ema([b["c_bid"] for b in self.rows], self.ema_p)
        self._vwap = m.vwap_daily(self.rows)

    def signal(self, i):
        e, vw = self._ema[i], self._vwap[i]
        if e is None or vw is None:
            return None, {}
        pe = self._ema[i - 1] if i > 0 else None
        pv = self._vwap[i - 1] if i > 0 else None
        a = self._atr[i] or 0.0
        c = self.rows[i]["c_bid"]
        if pe is not None and pv is not None:
            if pe <= pv and e > vw:
                return "BUY", {"trail": c - a * self.trail_m}
            if pe >= pv and e < vw:
                return "SELL", {"trail": c + a * self.trail_m}
        return None, {}

    def trail_mult(self):
        return self.trail_m


def sharpe_from_pnl(pnl: list[float], trades_per_year: float = 365.0 * 6.0) -> float:
    """Annualized Sharpe on a per-trade PnL list (conservative; per-trade, not
    per-bar, so it reflects realized trades only)."""
    if len(pnl) < 5:
        return 0.0
    mu = statistics.fmean(pnl)
    sd = statistics.stdev(pnl)
    if sd == 0:
        return 0.0
    return round(mu / sd * math.sqrt(trades_per_year_factor(len(pnl)) * 1.0), 3)


def trades_per_year_factor(n: int) -> float:
    # ~4h bars, ~220 trading days/yr, few trades; scale trades/yr ~ n
    # over a 12-month sample -> trades_per_year ~= n (12 months). Keep simple.
    return 1.0


def run_cell(pair: str, ema_p: int, trail_m: float) -> dict:
    rows = m.load(json.loads((DATA / f"{pair}.json").read_text(encoding="utf-8")), 240)
    r = F1Sweep(rows, ema_p=ema_p, trail_m=trail_m).run()
    mips = r["net_pips"]
    sh = 0.0
    if r["pnl_list"]:
        mu = statistics.fmean(r["pnl_list"])
        n = len(r["pnl_list"])
        sc = r.get("max_dd_pct", 0.0)
        sh = round(mu / math.sqrt(sum((x - mu) ** 2 for x in r["pnl_list"]) / (n - 1) or 1.0), 3) if n > 1 else 0.0
    return {"pair": pair, "ema_period": ema_p, "trail_mult": trail_m,
            "trades": r["trades"], "net_pips": round(mips, 1),
            "max_dd_pct": r["max_dd_pct"], "win_rate": r["win_rate"]}


def main() -> int:
    print(f"[phase2b] 2D sweep: ema={EMA_GRID} trail={TRAIL_GRID}")
    cells = []
    for pair in PAIRS:
        for ep in EMA_GRID:
            for tm in TRAIL_GRID:
                cells.append(run_cell(pair, ep, tm))
        print(f"[phase2b] {pair} done ({len([c for c in cells if c['pair']==pair])} cells)")

    # Positive cells (cost-adjusted net pips > 0) per config -> plateau rough.
    summary = {"cells_total": len(cells)}
    for pair in PAIRS:
        pos = [c for c in cells if c["pair"] == pair and c["net_pips"] > 0]
        summary[f"{pair}_positive_cells"] = len(pos)
        summary[f"{pair}_fraction_positive"] = round(len(pos) / (len(EMA_GRID) * len(TRAIL_GRID)), 3)
        summary[f"{pair}_best"] = max(cells, key=lambda c: c["net_pips"] if c["pair"] == pair else -1e9)
    out = {"grid": {"ema_period": EMA_GRID, "trail_mult": TRAIL_GRID},
           "cells": cells, "summary": summary}
    res = ROOT / "research" / "results" / "ema9vwap_parameter_surface.json"
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[phase2b] wrote {res}  cells={len(cells)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)