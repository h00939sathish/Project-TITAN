"""Provenance check: HF `rashedurzaman1/forex-data` 1-sec EURUSD vs local Dukascopy 1m bars.

Resamples the HF 1-second bid/ask OHLC into 1-minute bars using the same
convention as scripts/dukascopy_bi5.py aggregate_1m() (floor minute, o=first,
h/l=max/min, c=last, UTC), then aligns bar-by-bar against
research/dukascopy_1m_ba_prior/EURUSD.json for two auto-picked overlap windows.

Output: stats per window - bar counts, alignment, price drift in pips (1e4).
"""
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

PRIOR = Path(r"D:\projects\Project TITAN\research\dukascopy_1m_ba_prior\EURUSD.json")
HF_URL = ("https://huggingface.co/datasets/rashedurzaman1/forex-data/resolve/main/"
          "7865328_merged.parquet")
OUT = Path(r"D:\projects\Project TITAN\research\exp_fx_002")
PIP = 1e4  # EURUSD 1 pip


def load_local_bars() -> pd.DataFrame:
    """Read EURUSD.json safely (the puller may rewrite it concurrently)."""
    for attempt in range(10):
        tmp = Path(tempfile.gettempdir()) / f"eurusd_snapshot_{time.time()}.json"
        try:
            shutil.copy2(PRIOR, tmp)
            bars = json.loads(tmp.read_text(encoding="utf-8"))
            tmp.unlink(missing_ok=True)
            df = pd.DataFrame(bars)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df.sort_values("timestamp").reset_index(drop=True)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            if attempt == 9:
                raise
            time.sleep(5)
    raise RuntimeError("unreachable")


def pick_windows(local: pd.DataFrame, n_days: int = 7, n_win: int = 2) -> list[tuple]:
    """Pick best windows: rolling 7-calendar-day windows with most local bars."""
    local["day"] = local["timestamp"].dt.date
    per_day = local.groupby("day").size()
    d0_all = min(per_day.index)
    d1_all = max(per_day.index)
    scored = []
    d = d0_all
    while d + timedelta(days=n_days - 1) <= d1_all:
        d1 = d + timedelta(days=n_days - 1)
        total = sum(per_day.get(d + timedelta(days=k), 0) for k in range(n_days))
        scored.append((total, d, d1))
        d += timedelta(days=1)
    scored.sort(reverse=True)
    picked = []
    for _, d0, d1 in scored[:n_win * 3]:
        if all(d0 > p[1] or d1 < p[0] for p in picked):
            picked.append((d0, d1))
        if len(picked) == n_win:
            break
    return picked


def fetch_hf_minutes(d0, d1) -> pd.DataFrame:
    """Pull HF 1-sec rows for [d0, d1] via duckdb range-pushdown over HTTPS."""
    q = f"""
        SELECT timestamp, bid_open, bid_high, bid_low, bid_close,
               ask_open, ask_high, ask_low, ask_close
        FROM read_parquet('{HF_URL}')
        WHERE timestamp >= TIMESTAMPTZ '{d0} 00:00:00'
          AND timestamp <  TIMESTAMPTZ '{d1 + timedelta(days=1)} 00:00:00'
    """
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC';")
    con.execute("SET enable_http_metadata_cache = true;")
    t0 = time.time()
    df = con.execute(q).df()
    dt = time.time() - t0
    print(f"  [hf] {len(df):,} 1-sec rows for {d0}..{d1} (fetch {dt:.1f}s)", flush=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def resample_hf(df: pd.DataFrame) -> pd.DataFrame:
    """1-sec -> 1m with the dukascopy_bi5.aggregate_1m convention (UTC floors)."""
    df["m"] = df["timestamp"].dt.floor("min")
    g = df.groupby("m")
    out = pd.DataFrame({
        "timestamp": g["m"].first(),
        "o_bid": g["bid_open"].first(),
        "h_bid": g["bid_high"].max(),
        "l_bid": g["bid_low"].min(),
        "c_bid": g["bid_close"].last(),
        "o_ask": g["ask_open"].first(),
        "h_ask": g["ask_high"].max(),
        "l_ask": g["ask_low"].min(),
        "c_ask": g["ask_close"].last(),
        "n": g["m"].count(),
    })
    return out.reset_index(drop=True)


def compare_window(local: pd.DataFrame, hf: pd.DataFrame, d0, d1):
    d0s, d1s = d0, d1
    lw = local[(local["timestamp"].dt.date >= d0) & (local["timestamp"].dt.date <= d1s)]
    hw = hf[(hf["timestamp"].dt.date >= d0) & (hf["timestamp"].dt.date <= d1s)]
    lset, hset = set(lw["timestamp"]), set(hw["timestamp"])
    both = sorted(lset & hset)
    only_l, only_h = sorted(lset - hset), sorted(hset - lset)
    print(f"\n=== window {d0} .. {d1} ===")
    print(f"  local bars: {len(lw):,}   hf bars: {len(hw):,}   "
          f"matched: {len(both):,}   only-local: {len(only_l):,}   only-hf: {len(only_h):,}")
    if not both:
        print("  NO OVERLAP - nothing to compare")
        return
    m_l = lw.set_index("timestamp").loc[both]
    m_h = hw.set_index("timestamp").loc[both]
    diffs = pd.DataFrame({
        "c_bid": (m_l["c_bid"] - m_h["c_bid"]).abs() * PIP,
        "c_ask": (m_l["c_ask"] - m_h["c_ask"]).abs() * PIP,
        "h_bid": (m_l["h_bid"] - m_h["h_bid"]).abs() * PIP,
        "l_bid": (m_l["l_bid"] - m_h["l_bid"]).abs() * PIP,
        "o_bid": (m_l["o_bid"] - m_h["o_bid"]).abs() * PIP,
    })
    print("  drift (pips, local - hf):")
    for col in diffs.columns:
        s = diffs[col]
        print(f"    {col:6s} mean={s.mean():7.3f} p95={s.quantile(.95):7.3f} "
              f"max={s.max():7.3f}  | d>0.5pip: {(s > 0.5).sum()} bars")
    # exact-close agreement rate (float-noise tolerant)
    exact = (diffs["c_bid"] < 1e-8 * PIP).mean()
    print(f"  exact c_bid match: {exact * 100:.2f}%")
    if only_l[:3]:
        print(f"  only-local sample: {[str(t) for t in only_l[:3]]}")
    if only_h[:3]:
        print(f"  only-hf   sample: {[str(t) for t in only_h[:3]]}")


def main():
    print("loading local EURUSD.json...", flush=True)
    local = load_local_bars()
    print(f"  {len(local):,} bars, {local['timestamp'].min()} .. {local['timestamp'].max()}")
    wins = pick_windows(local)
    if not wins:
        print("could not find contiguous windows in local data")
        sys.exit(1)
    print("overlap windows:", wins)
    for d0, d1 in wins:
        df = fetch_hf_minutes(d0, d1)
        hf = resample_hf(df)
        compare_window(local, hf, d0, d1)


if __name__ == "__main__":
    main()
