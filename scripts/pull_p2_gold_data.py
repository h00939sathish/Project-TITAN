"""P2 (gold macro-momentum) acquisition.

Acquires the three datasets the debated P2 needs (not in repo):
1. DFII10 — 10-yr real yield, official FRED CSV (matches research/fred/{id}.csv).
2. DBC — Invesco DB Commodity Index ETF, yfinance.
3. XAUUSD — spot gold, yfinance `XAUUSD=X` (free tier, ADR-015-named source).

Free, evidence-led, no fabrication. yfinance is a research source, not a broker.
"""
import argparse
import csv
import datetime as dt
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRED_DIR = ROOT / "research" / "fred"
GOLD_DIR = ROOT / "research" / "gold_assets"


def fetch_fred_csv(series_id="DFII10"):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "titan-research"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read().decode("utf-8")
    rows = []
    cur = csv.DictReader(io.StringIO(raw))
    for row in cur:
        val = row.get(series_id)
        if val and val not in ("", "."):
            rows.append((row["observation_date"], float(val)))
    return rows


def fetch_yf_daily(symbol):
    import yfinance as yf
    t = yf.Ticker(symbol)
    df = t.history(period="max", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance empty for {symbol}")
    out = []
    for ts, r in df.iterrows():
        pdt = ts.date() if hasattr(ts, "date") else ts
        out.append({"date": pdt.isoformat(),
                    "open": round(float(r["Open"]), 4),
                    "high": round(float(r["High"]), 4),
                    "low": round(float(r["Low"]), 4),
                    "close": round(float(r["Close"]), 4),
                    "volume": int(r["Volume"] or 0)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fred", default=False, action="store_true")
    ap.add_argument("--skip-yf", default=False, action="store_true")
    args = ap.parse_args()

    FRED_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_fred:
        print("== DFII10 (10yr real yield) via FRED ==", flush=True)
        try:
            d = fetch_fred_csv("DFII10")
            out = FRED_DIR / "DFII10.csv"
            with open(out, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["observation_date", "DFII10"])
                for date_s, v in d:
                    w.writerow([date_s, v])
            print(f"  wrote {len(d)} rows -> {out} "
                  f"({d[0][0]}..{d[-1][0]})", flush=True)
        except Exception as e:
            print(f"  FRED DFII10 FAILED: {e}", flush=True)
    else:
        print("== skipping FRED (--skip-fred) ==")

    if not args.skip_yf:
        print("== DBC + XAUUSD via yfinance ==", flush=True)
        for sym, name in (("DBC", "dbc"), ("XAUUSD=X", "xauusd")):
            try:
                rows = fetch_yf_daily(sym)
                out = GOLD_DIR / f"{name}_daily.json"
                out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
                print(f"  {sym}: {len(rows)} rows {rows[0]['date']}..{rows[-1]['date']} "
                      f"-> {out}", flush=True)
            except Exception as e:
                print(f"  {sym} FAILED: {e}", flush=True)


if __name__ == "__main__":
    main()