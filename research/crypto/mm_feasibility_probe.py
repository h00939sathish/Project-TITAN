"""CRYPTO-005 exploratory feasibility probe (can_qualify=False, ADR-031 exploratory tier).

Trade-tape maker model from Binance um daily aggTrades:
- maker fill event = aggressor-side reversal (a resting order at the previous
  aggressor's price is crossed when the tape flips side)
- half_spread proxy = |reversal_price - entry_price| / 2
- markout(h) = adverse drift of the local price reference after the fill at
  1s / 5s / 60s
- net edge = half_spread - maker_fee - markout(h)

Uses IN-SAMPLE months only. Output gates the bulk data-acquisition decision;
it can never qualify a promotion.
"""
from __future__ import annotations

import csv
import io
import json
import random
import statistics
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from download_binance_trades import DEST, checksum, fetch  # reuse downloader conventions

MAKER_FEE = 0.0002  # binance_usdt_vip0_2026-08-14 label
HORIZONS_MS = {"1s": 1_000, "5s": 5_000, "60s": 60_000}
MID_WINDOW = 5  # trades averaged into the post-horizon price reference
OUT = ROOT / "research" / "crypto" / "results" / "probes"
DATA_ROOT = ROOT / "research" / "crypto" / "data"


def ts_to_ms(raw: str) -> int:
    v = int(raw)
    if v > 10**17:  # µs timestamps (Vision um daily files, 2025-01-01+)
        return v // 1000
    if v > 10**14:  # ms
        return v
    return v * 1000  # seconds


def load_day(symbol: str, day: str) -> list[tuple[int, float, bool]]:
    """Return (t_ms, price, buyer_is_aggressor) for one symbol-day."""
    zp = DEST / symbol / f"{symbol}-aggTrades-{day}.zip"
    url = (f"https://data.binance.vision/data/futures/um/daily/aggTrades/"
           f"{symbol}/{symbol}-aggTrades-{day}.zip")
    if not zp.exists() and not fetch(url, zp):
        return []
    sidecar = DATA_ROOT / "checksums_trades.json"
    sums = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    key = str(zp.relative_to(DATA_ROOT))
    if key not in sums:
        sums[key] = checksum(zp)
        sidecar.write_text(json.dumps(sums, indent=2), encoding="utf-8")
    rows: list[tuple[int, float, bool]] = []
    with zipfile.ZipFile(zp) as z:
        with z.open(z.namelist()[0]) as f:
            raw = f.read().decode()
    for r in csv.reader(io.StringIO(raw)):
        if len(r) < 7 or not r[0].isdigit():
            continue
        rows.append((ts_to_ms(r[5]), float(r[1]), r[6].lower() == "false"))
    rows.sort(key=lambda x: x[0])
    return rows


def probe_symbol(symbol: str, days: list[str]) -> dict:
    edges: dict[str, list[float]] = {h: [] for h in HORIZONS_MS}
    n_trades = 0
    acc = {"half_spread": 0.0, "fee": 0.0, "markout_60s": 0.0}
    n_fills = 0
    for day in days:
        rows = load_day(symbol, day)
        n_trades += len(rows)
        if len(rows) < 100:
            continue
        ts = [r[0] for r in rows]
        px = [r[1] for r in rows]
        aggr = [r[2] for r in rows]  # True: buyer crossed the ask
        # j[h] only ever advances (monotonic) -> O(len(rows)) per day
        j = {h: 0 for h in HORIZONS_MS}
        run = {h: 0.0 for h in HORIZONS_MS}  # rolling sum over last MID_WINDOW prints
        for i in range(1, len(rows)):
            if aggr[i] == aggr[i - 1]:
                continue
            entry = px[i - 1]          # resting-side fill price (crossed touch)
            half = abs(px[i] - entry) / 2.0
            if half <= 0 or entry <= 0:
                continue
            sign = 1.0 if aggr[i] else -1.0  # we end long / short post-fill
            n_fills += 1
            fee = entry * MAKER_FEE
            acc["half_spread"] += half
            acc["fee"] += fee
            for h, dt in HORIZONS_MS.items():
                jj = j[h] if j[h] >= i - 1 else i - 1
                while jj + 1 < len(rows) and ts[jj + 1] - ts[i - 1] <= dt:
                    jj += 1
                j[h] = jj
                ref = statistics.fmean(px[jj + 1 - MID_WINDOW if jj + 1 >= MID_WINDOW else 0: jj + 1])
                markout = sign * (entry - ref)  # >0 = adverse
                if h == "60s":
                    acc["markout_60s"] += markout
                edges[h].append(half - fee - markout)
    out = {"symbol": symbol, "trades": n_trades, "fills": n_fills,
           "decomposition_mean_usd": {k: round(v / n_fills, 4) if n_fills else 0
                                      for k, v in acc.items()},
           "proxy_note": "half-spread proxy = |reversal price - touch|/2 conflates spread with drift; "
                         "necessary-condition screen only (exploratory tier)."}
    rng = random.Random(7)
    out = {"symbol": symbol, "trades": n_trades,
           "decomposition_mean_usd": {k: round(v / n_fills, 4) if n_fills else 0
                                      for k, v in acc.items()},
           "proxy_note": "half-spread proxy = |reversal price - touch|/2 conflates spread with drift; "
                         "necessary-condition screen only (exploratory tier)."}
    for h, e in edges.items():
        if len(e) < 50:
            out[h] = {"n": len(e), "usable": False}
            continue
        block = max(1, len(e) // 100)
        max_start = max(0, len(e) - block)
        boots = []
        for _ in range(500):
            vals = []
            for _b in range(100):
                s0 = rng.randrange(max_start + 1)
                vals.extend(e[s0:s0 + block])
            boots.append(statistics.fmean(vals))
        m = statistics.fmean(e)
        out[h] = {
            "n": len(e),
            "mean_edge_usd_per_fill": round(m, 4),
            "block_bootstrap_lb95": round(sorted(boots)[25], 4),
            "win_frac": round(sum(1 for x in e if x > 0) / len(e), 4),
        }
    return out


def main(start: date, end: date, symbols=("BTCUSDT",)) -> int:
    days = []
    c = start
    while c <= end:
        days.append(c.isoformat())
        c += timedelta(days=1)
    res = {"probe": "CRYPTO-005-feasibility", "can_qualify": False,
           "tier": "exploratory (ADR-031)", "is_range": f"{start}..{end}", "symbols": {}}
    for s in symbols:
        res["symbols"][s] = probe_symbol(s, days)
        print(json.dumps(res["symbols"][s], indent=2))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"CRYPTO-005-probe-{start}_{end}.json"
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    d0 = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2024, 6, 1)
    d1 = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2024, 6, 3)
    syms = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("BTCUSDT",)
    raise SystemExit(main(d0, d1, syms))
