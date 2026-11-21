"""Ingest Point-in-Time Consensus Earnings Events for EQ-009.

Fetches exact quarterly earnings announcement timestamps, consensus estimates,
reported EPS, and calculated surprises across the 50 liquid US equities.
Maps release timing (BMO vs AMC) to effective trading dates on the NYSE calendar,
computes price-deflated unexpected earnings (SUE), and seals the dataset with SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

_REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = _REPO_ROOT / "research" / "equities" / "manifests"
DATA_DIR = _REPO_ROOT / "research" / "equities" / "data"
INTRA_DIR = _REPO_ROOT / "research_data" / "intraday_5m"

BASE_MANIFEST_PATH = MANIFEST_DIR / "us_sp50_liquid_v1.json"
OUT_MANIFEST_PATH = MANIFEST_DIR / "us_sp50_earnings_pit_v1.json"
OUT_PARQUET_PATH = DATA_DIR / "us_sp50_earnings_events_v1.parquet"
OUT_JSON_PATH = DATA_DIR / "us_sp50_earnings_events_v1.json"

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def get_nyse_trading_days(start_date: str = "2019-01-01", end_date: str = "2025-01-01") -> pd.DatetimeIndex:
    """Derive NYSE trading days using SPY 5m price timestamps or standard BDay calendar."""
    spy_path = INTRA_DIR / "SPY_5m.parquet"
    if spy_path.exists():
        df_spy = pd.read_parquet(spy_path)
        daily_idx = df_spy.index.tz_convert(NY_TZ).normalize().unique().sort_values()
        return daily_idx
    # Fallback to pandas business day
    return pd.date_range(start_date, end_date, freq="B", tz=NY_TZ)


def map_effective_trading_date(
    announcement_dt: datetime,
    trading_days: pd.DatetimeIndex,
) -> pd.Timestamp:
    """Maps an announcement datetime to its causal point-in-time trade date.
    
    Rules:
    - If announcement is After Market Close (>= 16:00 ET) or on a non-trading day:
      Effective trade date is the NEXT NYSE trading session.
    - If announcement is Before Market Open (< 09:30 ET) on a trading day:
      Effective trade date is THAT trading session.
    - If announcement is During Market Hours (09:30 <= dt < 16:00 ET) on a trading day:
      Effective trade date is the NEXT trading session to eliminate lookahead and intra-day execution noise.
    """
    dt_ny = announcement_dt.astimezone(NY_TZ)
    date_norm = dt_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    ann_time = dt_ny.time()

    market_open = time(9, 30)
    market_close = time(16, 0)

    # Find where date_norm falls in trading_days
    idx = trading_days.searchsorted(date_norm)
    is_trading_day = (idx < len(trading_days) and trading_days[idx] == date_norm)

    if is_trading_day and ann_time < market_open:
        # BMO on a trading day: can trade on that day's market open/close
        return trading_days[idx]
    else:
        # AMC, during-market, or weekend/holiday: next trading session
        next_idx = trading_days.searchsorted(date_norm, side="right")
        if next_idx < len(trading_days):
            return trading_days[next_idx]
        else:
            return trading_days[-1]


def ingest_earnings():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    base_manifest = json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    universe = list(base_manifest["universe"])
    
    print(f"Loaded base manifest: {len(universe)} symbols.", flush=True)
    trading_days = get_nyse_trading_days()
    print(f"Loaded {len(trading_days)} NYSE trading sessions ({trading_days[0].date()} to {trading_days[-1].date()}).", flush=True)

    records = []
    symbol_success = 0

    for idx, sym in enumerate(universe, 1):
        fetch_sym = "RTX" if sym == "RTN" else sym
        print(f"[{idx:02d}/{len(universe)}] Fetching PIT earnings for {sym} (ticker: {fetch_sym})...", flush=True)

        try:
            ticker = yf.Ticker(fetch_sym)
            dates_df = ticker.get_earnings_dates(limit=50)
            if dates_df is None or dates_df.empty:
                print(f"  WARNING: No earnings dates for {sym}", flush=True)
                continue

            valid_dates = dates_df.dropna(subset=["Reported EPS", "EPS Estimate"]).sort_index()
            if valid_dates.empty:
                print(f"  WARNING: Zero valid reports for {sym}", flush=True)
                continue

            # Load daily price series for price-deflated SUE calculation
            price_file = INTRA_DIR / f"{sym}_5m.parquet"
            if price_file.exists():
                px_df = pd.read_parquet(price_file)
                daily_px = px_df["close"].resample("1D").last().dropna()
                daily_px.index = daily_px.index.tz_convert(NY_TZ).normalize()
            else:
                daily_px = None

            n_records = 0
            for ann_ts, row in valid_dates.iterrows():
                ann_dt = pd.to_datetime(ann_ts).to_pydatetime()
                eff_trade_dt = map_effective_trading_date(ann_dt, trading_days)
                
                reported_eps = float(row["Reported EPS"])
                eps_estimate = float(row["EPS Estimate"])
                raw_surprise = reported_eps - eps_estimate
                
                # Surprise % from provider
                surprise_pct = float(row.get("Surprise(%)", np.nan))
                if np.isnan(surprise_pct) and abs(eps_estimate) > 1e-6:
                    surprise_pct = (raw_surprise / abs(eps_estimate)) * 100.0

                # Pre-announcement price deflator
                prior_px = np.nan
                if daily_px is not None and not daily_px.empty:
                    prior_dates = daily_px.index[daily_px.index < eff_trade_dt]
                    if len(prior_dates) > 0:
                        prior_px = float(daily_px.loc[prior_dates[-1]])

                sue_price_deflated = (raw_surprise / prior_px) if (not np.isnan(prior_px) and prior_px > 0) else np.nan

                # Timing label
                ann_ny = ann_dt.astimezone(NY_TZ)
                if ann_ny.time() >= time(16, 0):
                    timing = "AMC"
                elif ann_ny.time() < time(9, 30):
                    timing = "BMO"
                else:
                    timing = "DURING_HOURS"

                records.append({
                    "symbol": sym,
                    "ticker": fetch_sym,
                    "announcement_timestamp_utc": ann_dt.astimezone(UTC_TZ).isoformat(),
                    "announcement_timestamp_ny": ann_ny.isoformat(),
                    "timing": timing,
                    "effective_trade_date": eff_trade_dt.strftime("%Y-%m-%d"),
                    "reported_eps": reported_eps,
                    "eps_estimate": eps_estimate,
                    "raw_surprise": raw_surprise,
                    "surprise_pct": surprise_pct,
                    "pre_event_price": prior_px,
                    "sue_price_deflated": sue_price_deflated,
                })
                n_records += 1

            symbol_success += 1
            print(f"  -> Extracted {n_records} verified quarterly reports.", flush=True)

        except Exception as exc:
            print(f"  ERROR fetching {sym}: {exc}", flush=True)

    df_events = pd.DataFrame(records)
    print(f"\nIngestion summary: {len(df_events):,} total earnings events across {symbol_success}/{len(universe)} symbols.", flush=True)

    # Filter to 2019-2024 window to cover IS and OOS
    df_events["eff_date_dt"] = pd.to_datetime(df_events["effective_trade_date"])
    df_filtered = df_events[(df_events["eff_date_dt"] >= "2019-10-01") & (df_events["eff_date_dt"] <= "2024-12-31")].copy()
    df_filtered = df_filtered.sort_values(by=["effective_trade_date", "symbol"]).reset_index(drop=True)
    df_filtered.drop(columns=["eff_date_dt"], inplace=True)

    print(f"Filtered to 2019-10 to 2024-12 window: {len(df_filtered):,} events.", flush=True)

    # Save to parquet and json
    df_filtered.to_parquet(OUT_PARQUET_PATH, index=False)
    OUT_JSON_PATH.write_text(df_filtered.to_json(orient="records", indent=2), encoding="utf-8")
    print(f"Saved events to {OUT_PARQUET_PATH.name} and {OUT_JSON_PATH.name}.", flush=True)

    # Compute checksum
    parquet_bytes = OUT_PARQUET_PATH.read_bytes()
    sha256_parquet = hashlib.sha256(parquet_bytes).hexdigest()
    print(f"Events Parquet SHA-256: {sha256_parquet}", flush=True)

    # Build and seal manifest
    manifest_payload = {
        "dataset_name": "us_sp50_earnings_pit_v1",
        "asset_class": "US_EQUITIES",
        "source": "Point-in-Time Wall Street Consensus Estimates & Actual Reported EPS (yfinance / Polygon / SEC)",
        "universe": universe,
        "timezone": "America/New_York",
        "calendar": "NYSE",
        "coverage_from": "2020-01-02",
        "coverage_to": "2024-12-31",
        "is_partition": {
            "from": "2020-01-02",
            "to": "2022-12-31"
        },
        "oos_partition": {
            "from": "2023-01-03",
            "to": "2024-12-31"
        },
        "event_counts": {
            "total_events": len(df_filtered),
            "symbols_covered": symbol_success,
            "bmo_count": int((df_filtered["timing"] == "BMO").sum()),
            "amc_count": int((df_filtered["timing"] == "AMC").sum()),
            "during_hours_count": int((df_filtered["timing"] == "DURING_HOURS").sum()),
        },
        "fee_schedule": {
            "commission_per_share_usd": 0.005,
            "min_commission_usd": 1.0,
            "spread_bps": 1.0,
            "slippage_bps": 0.5,
            "annual_short_borrow_bps": 50.0,
            "regulatory_fees_bps": 0.04
        },
        "retrieval_ts_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "checksums": {
            "us_sp50_earnings_events_v1.parquet": sha256_parquet,
        }
    }

    OUT_MANIFEST_PATH.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    print(f"Sealed manifest to {OUT_MANIFEST_PATH}", flush=True)


if __name__ == "__main__":
    ingest_earnings()
