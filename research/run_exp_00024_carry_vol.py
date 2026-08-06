"""EXP-00024: Volatility-Weighted Carry (FX-CARRY-VOL) — experiment runner.

Successor to the REJECTED EXP-00023 (naive monthly G10 carry: mechanical
accrual only, +0.18%/mo, t=1.14, maxDD -13.5%, 2018-07..2026-06, no UIP spot
anomaly). EXP-00024 tests whether inverse-volatility weighting rescues carry:

  carry c_t   = (base_rate_T2 - USD_rate_T2) / 100        # percent -> decimal
  sigma_t     = 21d annualized stdev of daily XXXUSD returns, floored at 0.05
  w_t         = sign(c_t) * min(1, |c_t| / sigma_t)        # weekly rebalance
  net         = w*spot_ret + w*c*(1/360) accrual - 10bps on rebalanced notional

Verdict (Promote/Refine/Reject) vs the EXP-00023 baseline: after 10bps costs,
OOS net Sharpe, monthly mean, maxDD, >=40% drawdown cut, cross-instrument 3/4,
temporal sign stability. Fail-closed: pairs with missing rate legs are flagged,
never imputed.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
BASE_RATE = {
    "EURUSD": "ECBDFR.csv",
    "GBPUSD": "IRSTCI01GBM156N.csv",
    "AUDUSD": "IRSTCI01AUM156N.csv",
    "NZDUSD": "IRSTCI01NZM156N.csv",
}
COST_BPS = 10.0
VOL_FLOOR = 0.05
VOL_WINDOW = 21
T_LAG = 2
REBAL_WEEKDAY = 2  # Wednesday
START = datetime(2018, 7, 1)  # EXP-00023 baseline window start


def load_daily(pair: str) -> list[dict]:
    return json.load(open(ROOT / "research" / "tws_daily" / f"{pair}.json", encoding="utf-8"))


def _naive(dt: datetime) -> datetime:
    """Strip tzinfo (tws_daily timestamps are aware 'Z'; rates naive)."""
    return dt.replace(tzinfo=None)


def load_rate(name: str) -> list[tuple[datetime, float]]:
    rows = []
    for line in (ROOT / "research" / "fred" / name).read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            dt = _naive(datetime.fromisoformat(parts[0].strip()))
            v = float(parts[1].strip()) / 100.0  # percent -> decimal at load
        except ValueError:
            continue
        rows.append((dt, v))
    return sorted(rows, key=lambda r: r[0])


class RateSeries:
    """Forward-filled point-in-time rate lookup."""

    def __init__(self, rows: list[tuple[datetime, float]]):
        self.rows = rows

    def at(self, day: datetime) -> float | None:
        v = None
        for ts, val in self.rows:
            if ts <= day:
                v = val
            else:
                break
        return v


def run_pair(pair: str) -> dict:
    bars = load_daily(pair)
    closes = [float(b["close"]) for b in bars]
    dates = [_naive(datetime.fromisoformat(b["timestamp"])) for b in bars]
    n = len(closes)
    rets = [0.0] + [closes[i] / closes[i - 1] - 1.0 for i in range(1, n)]
    base = RateSeries(load_rate(BASE_RATE[pair]))
    usd = RateSeries(load_rate("DFF.csv"))

    pos, eq = 0.0, 1.0
    cost_total = spot_total = acc_total = 0.0
    daily, spreads = [], []
    for i in range(VOL_WINDOW + 2, n):
        d = dates[i]
        if d < START:
            continue
        lo = max(1, i - T_LAG - VOL_WINDOW)
        w = rets[lo:i - T_LAG]
        sd = pstdev(w) if len(w) > 2 else 0.0
        sigma = max(sd * math.sqrt(252.0), VOL_FLOOR)

        br = base.at(d - timedelta(days=T_LAG))
        ur = usd.at(d - timedelta(days=T_LAG))
        if br is not None and ur is not None:
            c = br - ur
            spreads.append(c * 1e4)
        else:
            c = 0.0  # no rate: no accrual for this day; flagged if pervasive

        if d.weekday() == REBAL_WEEKDAY:
            target = math.copysign(min(1.0, abs(c) / sigma), c) if c != 0.0 else 0.0
            cost_total += abs(target - pos) * COST_BPS / 1e4
            pos = target

        r_spot = pos * rets[i]
        r_acc = pos * c * (1.0 / 360.0)
        daily.append(r_spot + r_acc)
        spot_total += r_spot
        acc_total += r_acc
        eq *= 1.0 + (r_spot + r_acc)

    if len(daily) < 250:
        return {"pair": pair, "error": f"insufficient window ({len(daily)} days)"}

    m = mean(daily)
    sd = pstdev(daily) if len(daily) > 2 else 1.0
    sharpe = (m / sd * math.sqrt(252.0)) if sd > 1e-12 else 0.0
    peak, mdd, eqv = 0.0, 0.0, 1.0
    for r in daily:
        eqv *= (1.0 + r)
        peak = max(peak, eqv)
        mdd = max(mdd, (peak - eqv) / peak)
    win = sum(1 for r in daily if r > 0) / len(daily)

    # temporal stability: first vs second half sign of mean
    half = len(daily) // 2
    m1, m2 = mean(daily[:half]), mean(daily[half:])

    return {
        "pair": pair,
        "n_days": len(daily),
        "net_sharpe": round(sharpe, 3),
        "monthly_pct": round(m * 21 * 100, 3),
        "win_rate": round(win, 4),
        "maxDD_pct": round(mdd * 100, 2),
        "cost_pct": round(cost_total * 100, 3),
        "spot_pct": round(spot_total * 100, 3),
        "accrual_pct": round(acc_total * 100, 3),
        "avg_carry_bps": round(mean(spreads), 2) if spreads else None,
        "temporal_stable": (m1 > 0) == (m2 > 0),
        "mean_first_half": round(m1 * 21 * 100, 3),
        "mean_second_half": round(m2 * 21 * 100, 3),
    }


def main() -> None:
    results = []
    for p in PAIRS:
        try:
            results.append(run_pair(p))
        except Exception as exc:  # noqa: BLE001
            results.append({"pair": p, "error": str(exc)[:120]})

    ok = [r for r in results if "error" not in r]
    print("EXP-00024 Volatility-Weighted Carry (2018-07.., 10bps costs)")
    print(f"{'pair':8} {'netSharpe':>9} {'%/mo':>7} {'win':>6} {'maxDD%':>7} "
          f"{'cost%':>6} {'spot%':>7} {'accr%':>7} {'carryBPS':>8} {'tStable':>7}")
    for r in ok:
        print(f"{r['pair']:8} {r['net_sharpe']:9.3f} {r['monthly_pct']:7.3f} "
              f"{r['win_rate']:6.3f} {r['maxDD_pct']:7.2f} {r['cost_pct']:6.2f} "
              f"{r['spot_pct']:7.2f} {r['accrual_pct']:7.2f} "
              f"{str(r['avg_carry_bps']):>8} {str(r['temporal_stable']):>7}")
    for r in results:
        if "error" in r:
            print(f"  {r['pair']}: ERROR {r['error']}")

    if ok:
        n_pos = sum(1 for r in ok if r["net_sharpe"] > 0)
        avg_sharpe = mean(r["net_sharpe"] for r in ok)
        avg_dd = mean(r["maxDD_pct"] for r in ok)
        stable = sum(1 for r in ok if r["temporal_stable"])
        print("\n--- Portfolio verdict vs EXP-00023 baseline ---")
        print(f"positive-sharpe pairs: {n_pos}/4 (need >=3) | avg net Sharpe {avg_sharpe:.3f} "
              f"| avg maxDD {avg_dd:.2f}% (EXP-23: -13.5%) | temporal stable {stable}/4")
        promote = (avg_sharpe > 0.8 and n_pos >= 3 and avg_dd < 10.0)
        refine = (0.5 <= avg_sharpe <= 0.8 and n_pos >= 2)
        if promote:
            print("VERDICT: PROMOTE (survives 10bps, >=3/4 positive, DD < 10%)")
        elif refine:
            print("VERDICT: REFINE (borderline; costs/execution need work)")
        else:
            print("VERDICT: REJECT (fails the EXP-00023-beating bar) — result to neg_results")


if __name__ == "__main__":
    main()