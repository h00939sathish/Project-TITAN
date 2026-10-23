#!/usr/bin/env python3
"""CRYPTO-006 feasibility probe (can_qualify=False, in-sample months only).

Frozen protocol: research/crypto/hypotheses/CRYPTO-006-prereg.json
Single variable vs CRYPTO-005: the instrument liquidity tier. Quote policy,
fill rule, VIP0 2bps maker fee, markout horizons, quote notional and
participation cap are held identical.

Fail-closed: the tape-reversal top-of-book proxy OVERESTIMATES maker PnL, so
proxy-negative => evidence-grade rejection; proxy-positive => certifies nothing
and only justifies paid historical L2 acquisition.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import math
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "research/crypto/manifests/binance_vision_widescap_v1.json"
RESULTS = REPO / "research/crypto/results/CRYPTO-006-probe.json"

MAKER_FEE_BPS = 2.0
QUOTE_NOTIONAL_USD = 1000.0
PARTICIPATION_CAP = 0.02
HORIZON_S = 60
PROBE_DAYS = [date(2025, 3, d) for d in range(10, 17)]
VOL_START_MS = 1733011200000  # 2024-12-01T00:00Z
VOL_END_MS = 1740699600000    # 2025-02-28T00:00Z (exclusive tail, 89 rows)
ONBOARD_MAX_MS = 1710028800000  # 2024-03-10T00:00Z
BAND_LO, BAND_HI, SAMPLE_N = 51, 150, 20
MIN_FILLS_7D = 230          # 1,000 fills/month/symbol pro-rated to 7 days
CONCENTRATION_DAY_FRACTION = 0.30
BOOTSTRAP_REPS = 2000
SEED = 20260922

PEG_BASES = {
    "USDC", "FDUSD", "TUSD", "DAI", "USDE", "USDF", "BUSD", "USDR", "EURC",
    "EUR", "EURR", "TRY", "BRL", "ARS", "AUD", "GBP", "JPY", "COP", "MXN", "ZAR",
}
EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
KLINES = "https://fapi.binance.com/fapi/v1/klines"
AGG_URL = ("https://data.binance.vision/data/futures/um/daily/aggTrades"
           "/{s}/{s}-aggTrades-{d}.zip")


MAX_FILE_BYTES = 48_000_000
FETCH_DEADLINE_S = 45
DOWNLOAD_WORKERS = 8


def get(url: str, timeout: int = 45) -> bytes:
    """Bounded fetch. urllib's socket timeout does not bound a slow-drip body, so
    the read is deadline- and size-limited explicitly."""
    req = urllib.request.Request(url, headers={"User-Agent": "titan-research/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        deadline = time.monotonic() + FETCH_DEADLINE_S
        buf = io.BytesIO()
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            buf.write(chunk)
            if buf.tell() > MAX_FILE_BYTES:
                raise TimeoutError("file_too_large")
            if time.monotonic() > deadline:
                raise TimeoutError("read_deadline")
        return buf.getvalue()


def fetch_many(urls: list[str], timeout: int = 45) -> dict[str, tuple[bytes | None, str | None]]:
    """Prefetch concurrently so one stalled CDN stream cannot serialise the probe."""
    out: dict[str, tuple[bytes | None, str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futs = {pool.submit(get, u, timeout): u for u in urls}
        for fut in concurrent.futures.as_completed(futs):
            u = futs[fut]
            try:
                out[u] = (fut.result(), None)
            except Exception as exc:  # noqa: BLE001 - gap, recorded not hidden
                out[u] = (None, type(exc).__name__)
    return out


def _params(**kw: object) -> str:
    return "&".join(f"{k}={v}" for k, v in kw.items())


def _searchsorted(ts: list[int], target: int) -> int:
    lo, hi = 0, len(ts)
    while lo < hi:
        mid = (lo + hi) // 2
        if ts[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


# --------------------------------------------------------------- universe ---


def build_universe() -> tuple[list[str], dict, dict]:
    """Frozen ex-ante rule. Price-independent: no spread/return information."""
    snap = get(EXCHANGE_INFO, timeout=90)
    info = json.loads(snap)
    meta = {
        "exchange_info_sha256": hashlib.sha256(snap).hexdigest(),
        "snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "total_symbols": len(info["symbols"]),
    }
    tick: dict[str, float] = {}
    min_notional: dict[str, float] = {}
    for s in info["symbols"]:
        if (s.get("status") != "TRADING" or s.get("contractType") != "PERPETUAL"
                or s.get("quoteAsset") != "USDT"
                or int(s.get("onboardDate", 0)) > ONBOARD_MAX_MS
                or s.get("baseAsset") in PEG_BASES):
            continue
        t = m = None
        for f in s.get("filters", []):
            ft = f.get("filterType")
            if ft == "PRICE_FILTER":
                t = float(f["tickSize"])
            elif ft == "MIN_NOTIONAL":
                m = float(f["notional"])
        if t is None or m is None:
            continue
        if QUOTE_NOTIONAL_USD < m:      # G5: our quote must clear venue minimum
            continue
        tick[s["symbol"]], min_notional[s["symbol"]] = t, m
    eligible = sorted(min_notional)
    meta["eligible_after_filters"] = len(eligible)

    vol: dict[str, float] = {}
    failed: list[str] = []
    rank_urls = {
        f"{KLINES}?{_params(symbol=sym, interval='1d', startTime=VOL_START_MS, endTime=VOL_END_MS)}": sym
        for sym in eligible
    }
    print(f"  [rank] {len(rank_urls)} symbols x 90d klines", file=sys.stderr)
    fetched_rank = fetch_many(list(rank_urls), timeout=25)
    for url, (raw, err) in fetched_rank.items():
        sym = rank_urls[url]
        if raw is None:
            failed.append(f"{sym}:{err}")
            continue
        try:
            vol[sym] = sum(float(r[7]) for r in json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{sym}:parse_{type(exc).__name__}")
    print(f"  [rank] done: {len(vol)} ranked, {len(failed)} failed", file=sys.stderr)
    meta["volume_rank_failures"] = len(failed)
    if failed:
        meta["volume_rank_failure_examples"] = failed[:5]

    ranked = sorted(vol, key=lambda k: -vol[k])
    band = ranked[BAND_LO - 1:BAND_HI]
    stride = max(1, len(band) // SAMPLE_N)
    picked = band[::stride][:SAMPLE_N]
    meta.update({
        "band_rank_lo": BAND_LO, "band_rank_hi": BAND_HI,
        "band_size": len(band), "stride": stride, "picked": len(picked),
        "tick_size": {p: tick[p] for p in picked},
        "min_notional": {p: min_notional[p] for p in picked},
        "volume_90d_usd": {p: round(vol[p], 2) for p in picked},
        "band_top_symbol": band[0] if band else None,
        "band_bottom_symbol": band[-1] if band else None,
    })
    return picked, meta, tick


# ------------------------------------------------------------- edge per day --


def day_fills(sym: str, day: date, raw: bytes | None, gap: str | None) -> dict | None:
    """Reversal-proxy maker fills for one symbol-day.

    A resting BUY fills when a taker SELL prints below the last taker BUY;
    a resting SELL fills when a taker BUY prints above the last taker SELL.
    Captured half-spread = |reversal gap| / 2 in bps of the prevailing mid.
    """
    if raw is None:
        return {"data_gap": gap or "no_data"}
    if not raw or raw[:2] != b"PK":
        return {"data_gap": "not_a_zip"}
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = [n for n in z.namelist() if n.endswith(".csv")] or z.namelist()
    ts: list[int] = []
    px: list[float] = []
    rec: list[tuple[int, float, float, bool]] = []
    with z.open(names[0]) as fh:
        for line in fh.read().decode().splitlines():
            line = line.strip()
            if not line or line.startswith("agg_trade_id"):
                continue
            p = line.split(",")
            if len(p) < 7:
                continue
            try:
                t_ms, price, qty = int(p[5]), float(p[1]), float(p[2])
                maker_buy = p[6].lower() in ("true", "1")
            except ValueError:
                continue
            if price <= 0 or qty <= 0:
                continue
            rec.append((t_ms, price, qty, maker_buy))
    if not rec:
        return {"fills": [], "trades": 0}
    rec.sort(key=lambda r: r[0])
    ts = [r[0] for r in rec]
    px = [r[1] for r in rec]

    last_buy_px: float | None = None   # price of last taker BUY
    last_sell_px: float | None = None  # price of last taker SELL
    fills: list[dict] = []

    def markout(entry: float, fill_ms: int, side: float) -> float:
        j = min(_searchsorted(ts, fill_ms + HORIZON_S * 1000), len(ts) - 1)
        exit_px = px[j]
        if entry <= 0:
            return 0.0
        return (exit_px - entry) / entry * 1e4 * side

    for t_ms, price, qty, maker_buy in rec:
        notional = price * qty
        clipped = notional * PARTICIPATION_CAP
        quote_usd = min(QUOTE_NOTIONAL_USD, clipped) if clipped > 0 else 0.0
        if maker_buy:            # aggressor SOLD -> our resting BUY filled -> LONG
            if last_buy_px is not None and last_buy_px > price:
                mid = (last_buy_px + price) / 2.0
                half = (last_buy_px - price) / mid * 1e4 / 2.0
                entry = price
                fills.append({
                    "ts": t_ms, "half_bps": half, "side": 1.0,
                    "net_bps": half - MAKER_FEE_BPS + markout(entry, t_ms, 1.0),
                    "usd": quote_usd, "entry": entry,
                })
            last_sell_px = price
        else:                    # aggressor BOUGHT -> our resting SELL filled -> SHORT
            if last_sell_px is not None and price > last_sell_px:
                mid = (price + last_sell_px) / 2.0
                half = (price - last_sell_px) / mid * 1e4 / 2.0
                entry = price
                fills.append({
                    "ts": t_ms, "half_bps": half, "side": -1.0,
                    "net_bps": half - MAKER_FEE_BPS + markout(entry, t_ms, -1.0),
                    "usd": quote_usd, "entry": entry,
                })
            last_buy_px = price
    return {"fills": fills, "trades": len(rec)}


def bootstrap_lb95(vals: list[float], rng: random.Random) -> float | None:
    n = len(vals)
    if n < 40:
        return None
    block = max(20, min(500, n // 10))
    means = []
    for _ in range(BOOTSTRAP_REPS):
        acc: list[float] = []
        while len(acc) < n:
            s = rng.randrange(0, n)
            acc.extend(vals[s:s + block])
        means.append(statistics.fmean(acc[:n]))
    means.sort()
    return means[int(0.05 * len(means))]


def concentration_days(daily_pnl: dict[str, float]) -> float:
    """Smallest number of probe days whose pnl covers all positive pnl, as a
    fraction of days used. 1.0 means no single day dominates."""
    tot = sum(v for v in daily_pnl.values() if v > 0)
    if tot <= 0:
        return 1.0
    ordered = sorted((v for v in daily_pnl.values() if v > 0), reverse=True)
    acc = run = 0.0
    for k, v in enumerate(ordered, 1):
        run += v
        if run >= tot:
            return k / max(1, len(daily_pnl))
    return 1.0


# --------------------------------------------------------------------- run --


def main() -> int:
    universe, meta, tick = build_universe()
    print(f"[universe] eligible={meta['eligible_after_filters']} "
          f"band={meta['band_size']} picked={len(universe)}", file=sys.stderr)
    print(f"[picked] {universe}", file=sys.stderr)

    per_sym: dict[str, dict] = {}
    gaps: dict[str, list[str]] = {}
    urls = {AGG_URL.format(s=sym, d=day.strftime("%Y-%m-%d")): (sym, day)
            for sym in universe for day in PROBE_DAYS}
    print(f"[tapes] fetching {len(urls)} files", file=sys.stderr)
    fetched = fetch_many(list(urls))
    by_key = {urls[u]: v for u, v in fetched.items()}
    done = 0
    for sym in universe:
        all_f: list[dict] = []
        trades = 0
        daily_fills: dict[str, int] = {}
        daily_pnl: dict[str, float] = {}
        for day in PROBE_DAYS:
            raw, gapr = by_key.get((sym, day), (None, "not_fetched"))
            r = day_fills(sym, day, raw, gapr)
            done += 1
            if done % 20 == 0:
                print(f"  [tapes] {done}/{len(urls)}", file=sys.stderr)
            if r is None or "data_gap" in r:
                gaps.setdefault(sym, []).append(f"{day}:{(r or {}).get('data_gap', 'none')}")
                continue
            trades += r["trades"]
            key = day.isoformat()
            daily_fills[key] = len(r["fills"])
            # pnl in USD: net bps applied to the clipped quote notional
            daily_pnl[key] = sum(f["net_bps"] / 1e4 * f["usd"] for f in r["fills"])
            all_f.extend(r["fills"])
        if not all_f:
            gaps.setdefault(sym, []).append("no_fills")
            continue
        net = [f["net_bps"] for f in all_f]
        half = [f["half_bps"] for f in all_f]
        rng = random.Random(SEED + hash(sym) % 9973)
        per_sym[sym] = {
            "trades": trades,
            "fills_7d": len(all_f),
            "median_half_spread_bps": statistics.median(half),
            "mean_half_spread_bps": statistics.fmean(half),
            "median_net_edge_bps": statistics.median(net),
            "mean_net_edge_bps": statistics.fmean(net),
            "bootstrap_lb95_net_bps": bootstrap_lb95(net, rng),
            "daily_fills": daily_fills,
            "daily_pnl_usd": {k: round(v, 4) for k, v in daily_pnl.items()},
            "pnl_usd_7d": round(sum(daily_pnl.values()), 4),
            "days_for_pnl_fraction": round(concentration_days(daily_pnl), 4),
        }

    if not per_sym:
        RESULTS.write_text(json.dumps({"outcome": "no_data", "universe": meta,
                                       "gaps": gaps}, indent=2))
        print(json.dumps({"outcome": "no_data"}, indent=2))
        return 1

    syms = sorted(per_sym)
    halves = [per_sym[s]["median_half_spread_bps"] for s in syms]
    mednets = [per_sym[s]["median_net_edge_bps"] for s in syms]
    lbs = [per_sym[s]["bootstrap_lb95_net_bps"] for s in syms
           if per_sym[s]["bootstrap_lb95_net_bps"] is not None]
    fills = [per_sym[s]["fills_7d"] for s in syms]
    conc = [per_sym[s]["days_for_pnl_fraction"] for s in syms]

    g1_frac = sum(1 for v in halves if v > MAKER_FEE_BPS) / len(halves)
    g2a = statistics.median(mednets) > 0
    g2b_frac = (sum(1 for v in lbs if v > 0) / len(lbs)) if lbs else 0.0
    g3_frac = sum(1 for v in fills if v >= MIN_FILLS_7D) / len(fills)
    g4_frac = sum(1 for v in conc if v >= CONCENTRATION_DAY_FRACTION) / len(conc)

    gates = {
        "G1_spread_gt_fee_symbol_frac": round(g1_frac, 4),
        "G1_pass": g1_frac >= 0.5,
        "G2a_median_net_edge_positive": bool(g2a),
        "G2b_lb95_positive_symbol_frac": round(g2b_frac, 4),
        "G2b_pass": g2b_frac >= 0.6,
        "G2_pass": bool(g2a and g2b_frac >= 0.6),
        "G3_capacity_symbol_frac": round(g3_frac, 4),
        "G3_pass": g3_frac >= 0.5,
        "G4_day_concentration_symbol_frac": round(g4_frac, 4),
        "G4_pass": g4_frac >= 0.5,
        "G5_execution_realism_pass": True,
        "thresholds": {"G1": ">=0.50", "G2a": "median>0", "G2b": ">=0.60",
                       "G3": ">=0.50 of symbols >=230 fills", "G4": ">=0.50"},
    }
    escalate = all(gates[k] for k in ("G1_pass", "G2_pass", "G3_pass", "G4_pass",
                                      "G5_execution_realism_pass"))

    outcome = "GATE_PASS_ESCALATE_TO_PAID_L2" if escalate else "probe_gated_rejection"
    first_fail = next((k for k in ("G1_pass", "G2_pass", "G3_pass", "G4_pass") if not gates[k]), None)

    out = {
        "hypothesis_id": "CRYPTO-006",
        "probe": True,
        "can_qualify": False,
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "research/crypto/hypotheses/CRYPTO-006-prereg.json",
        "maker_fee_bps": MAKER_FEE_BPS,
        "universe": meta,
        "symbols_evaluated": len(syms),
        "symbols": per_sym,
        "data_gaps": gaps,
        "summary": {
            "median_of_medians_half_spread_bps": round(statistics.median(halves), 4),
            "median_of_medians_net_edge_bps": round(statistics.median(mednets), 4),
            "half_spread_bps_range": [round(min(halves), 4), round(max(halves), 4)],
            "total_fills": int(sum(fills)),
            "pnl_usd_7d_total": round(sum(per_sym[s]["pnl_usd_7d"] for s in syms), 2),
        },
        "gates": gates,
        "first_failed_gate": first_fail,
        "outcome": outcome,
        "oos_partition_read": False,
        "classification_if_reject": "execution_constrained_rejection",
        "absorbing_negative_result": False,
        "proxy_note": ("Reversal proxy overestimates maker PnL (blind to sub-trade "
                       "quoted spread, queue position, cancel latency). Proxy-negative "
                       "is evidence-grade; proxy-positive certifies nothing."),
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=2, default=str))
    MANIFEST.write_text(json.dumps({
        "dataset_name": "binance_vision_widescap_v1", "venue": "Binance USDT-M",
        "source_url": "https://data.binance.vision/data/futures/um/daily/aggTrades",
        "licence": "Public historical market-data dumps published by Binance Vision; research use.",
        "retrieved_utc": out["ran_at_utc"], "universe": meta, "symbols": syms,
        "probe_days": [d.isoformat() for d in PROBE_DAYS],
        "governing_adr": "ADR-031",
    }, indent=2, default=str))
    print(json.dumps({"outcome": outcome, "first_failed_gate": first_fail,
                      "gates": gates, "summary": out["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
