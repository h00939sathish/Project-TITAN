"""TraderDev FX-major strategy sourcing (debated plan Step 1).

Pull the top-5 public strategies per FX pair (by marketplace profit ranking),
with their reported KPIs. SAVE metadata + ids ONLY — the marketplace's own
backtests are NEVER trusted as evidence (debated decision A); the KPIs are
recorded for bias documentation, not as candidate evidence.

Pairs: the 8 FX majors used by the project.
"""
import json
import urllib.request

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURGBP"]
N = 5
API = "https://mcp-api.trader.dev/strategies/search"


def _fetch(url, tries=5):
    import time
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def top_n(symbol, n=N):
    url = f"{API}?sort=profit&limit={n}&offset=0&symbol={symbol}"
    d = _fetch(url)
    out = []
    for r in d.get("results") or []:
        res = r.get("result") or {}
        out.append({
            "name": r.get("name"),
            "id": r.get("id"),
            "version": r.get("version"),
            "tf": r.get("timeframe"),
            "reported": {
                "sharpe": round(res.get("sharpeRatio") or 0, 2),
                "net_profit_pct": round(res.get("netProfitPct") or 0, 1),
                "pf": round(res.get("profitFactor") or 0, 2),
                "win_rate": round(res.get("winRatePct") or 0, 1),
                "trades": res.get("totalTrades"),
                "max_dd_pct": round(res.get("maxDrawdownPct") or 0, 1),
            },
            "fork_json_url": res.get("forkJsonUrl"),
        })
    return out


def main():
    out = {}
    for p in PAIRS:
        out[p] = top_n(p)
        print(f"{p}: {len(out[p])} top strategies", flush=True)
        import time
        time.sleep(4)
    import pathlib
    res = pathlib.Path("research/results/traderdev_fx_top5_sourced.json")
    res.parent.mkdir(parents=True, exist_ok=True)
    res.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {res}")


if __name__ == "__main__":
    main()