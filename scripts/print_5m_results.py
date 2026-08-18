import json
from pathlib import Path

res_path = Path("research/backtest_results_summary.json")
data = json.loads(res_path.read_text(encoding="utf-8"))

print(f"{'Strategy ID':22s} | {'SPY (5m)':10s} | {'QQQ (5m)':10s} | {'AAPL (5m)':10s} | {'MSFT (5m)':10s} | {'EURUSD (5m)':12s}")
print("-" * 80)

datasets_5m = {k: {r["strategy_id"]: r for r in v} for k, v in data.items() if "5m" in k}

strats = list(next(iter(datasets_5m.values())).keys())

for s in strats:
    spy_ret = datasets_5m.get("SPY [5m Intraday]", {}).get(s, {}).get("total_return_pct", 0.0)
    qqq_ret = datasets_5m.get("QQQ [5m Intraday]", {}).get(s, {}).get("total_return_pct", 0.0)
    aapl_ret = datasets_5m.get("AAPL [5m Intraday]", {}).get(s, {}).get("total_return_pct", 0.0)
    msft_ret = datasets_5m.get("MSFT [5m Intraday]", {}).get(s, {}).get("total_return_pct", 0.0)
    eur_ret = datasets_5m.get("EURUSD [5m Intraday]", {}).get(s, {}).get("total_return_pct", 0.0)
    
    print(f"{s:22s} | {spy_ret:+9.2f}% | {qqq_ret:+9.2f}% | {aapl_ret:+9.2f}% | {msft_ret:+9.2f}% | {eur_ret:+11.2f}%")
