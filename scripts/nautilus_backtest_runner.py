#!/usr/bin/env python3
"""Run all 5 strategy backtests in separate subprocesses and compare with TITAN results."""

import subprocess
import sys

strategies = [
    "Momentum(20)",
    "MA Cross(5,20)",
    "Dual MA(5,20)",
    "MeanRev(20,-2.0,-0.5)",
    "VolRegime(20,60,1.0)",
]

# TITAN experiment results for SPY OOS 2023-2024
titan = {
    "Momentum(20)":         {"return": 1.27, "cagr": 0.64, "sharpe": 1.2950, "mdd": 0.47, "wr": 37.5, "trades": 32, "fills": 32},
    "MA Cross(5,20)":       {"return": 1.71, "cagr": None, "sharpe": 1.5583, "mdd": 0.30, "wr": 30.8, "trades": 13, "fills": 13},
    "MeanRev(20,-2.0,-0.5)":{"return": None, "cagr": None, "sharpe": None, "mdd": None, "wr": None, "trades": 2, "fills": 2},
    "VolRegime(20,60,1.0)": {"return": 0.85, "cagr": 0.42, "sharpe": 1.0600, "mdd": 0.30, "wr": 50.0, "trades": 24, "fills": 24},
}

def match(a, b, tol_rel=0.3, tol_abs=0.3):
    if b is None or b == 0:
        return "N/A" if b is None else ("YES" if abs(a) < tol_abs else f"NO(d={abs(a):.2f})")
    return "YES" if abs(a - b) < max(abs(b) * tol_rel, tol_abs) else f"NO(d={abs(a-b):.2f})"

results = {}
for name in strategies:
    r = subprocess.run(
        [sys.executable, "scripts/nautilus_backtest_all.py", name],
        capture_output=True, text=True, timeout=120,
    )
    for line in r.stdout.splitlines():
        if line.startswith("RESULT|"):
            parts = line.strip().split("|")
            results[name] = {
                "return": float(parts[2]), "cagr": float(parts[3]), "sharpe": float(parts[4]),
                "mdd": float(parts[5]), "wr": float(parts[6]), "trades": int(parts[7]),
                "pf": float(parts[8]), "vol": float(parts[9]), "calmar": float(parts[10]),
            }
            print(f"  {name}: ret={results[name]['return']:.2f}% sharpe={results[name]['sharpe']:.4f} trades={results[name]['trades']}")
            break

print(f"\n{'='*85}")
print(f"  Cross-Validation: NautilusTrader vs TITAN Engine (SPY OOS 2023-2024)")
print(f"{'='*85}")

hdr = f"  {'Strategy':<25} {'Metric':<8} {'Nautilus':>10} {'TITAN':>10}  {'Match':>8}"
print(hdr)
print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")

for name in strategies:
    r = results.get(name, {})
    t = titan.get(name, {})
    if not r:
        continue
    for met, key in [("Ret%", "return"), ("CAGR", "cagr"), ("Sharpe", "sharpe"),
                     ("DD%", "mdd"), ("Win%", "wr"), ("Trades", "trades")]:
        nv = r.get(key, 0)
        tv = t.get(key)
        if tv is None:
            m = "N/A"
        elif key == "trades":
            m = "YES" if nv == tv else f"NO(d={abs(nv-tv)})"
        elif key in ("mdd",):
            m = match(abs(nv), abs(tv), 0.3, 0.3)
        elif key in ("wr",):
            m = match(nv, tv, 0.3, 10)
        else:
            m = match(nv, tv, 0.3, 0.3)
        tv_str = f"{tv:.2f}" if tv is not None else "N/A"
        print(f"  {name:<25} {met:<8} {nv:>10.2f} {tv_str:>10}  {m:>8}")

print(f"\n  Notes:")
print(f"  - Separate subprocess per strategy (no logging conflicts)")
print(f"  - Market orders fill at next-bar open (vs TITAN's close-of-bar)")
print(f"  - No commissions/slippage modeled in nautilus runs")
print(f"  - Dual MA has no TITAN SPY experiment (rejected control)")
print(f"  - MeanRev SPY triggered 2 trades in TITAN vs {results.get('MeanRev(20,-2.0,-0.5)', {}).get('trades', '?')} in nautilus")
