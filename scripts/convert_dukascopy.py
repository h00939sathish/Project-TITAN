"""Convert Dukascopy 1m bid/ask data into standard TITAN OHLCV 5m and Daily formats.

Uses midpoint pricing ((ask+bid)/2) and tick count (n) as volume.
Outputs to research/fx_clean_5m and research/fx_clean_daily.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
DUKA_DIR = ROOT_DIR / "research" / "dukascopy_1m_ba"
OUT_5M_DIR = ROOT_DIR / "research" / "fx_clean_5m"
OUT_DAILY_DIR = ROOT_DIR / "research" / "fx_clean_daily"


def convert_file(input_path: Path):
    symbol = input_path.stem
    print(f"Processing {symbol}...")
    
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if not data:
        print(f"  Empty data for {symbol}")
        return

    # Convert to standard 1m midpoint bars
    standard_bars = []
    for row in data:
        # Use midpoint for O, H, L, C
        o = (row["o_ask"] + row["o_bid"]) / 2
        h = (row["h_ask"] + row["h_bid"]) / 2
        l = (row["l_ask"] + row["l_bid"]) / 2
        c = (row["c_ask"] + row["c_bid"]) / 2
        v = row["n"]  # Tick count
        
        standard_bars.append({
            "timestamp": row["timestamp"],
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": v
        })
        
    # Aggregate into 5m
    bars_5m = _resample(standard_bars, target_minutes=5)
    OUT_5M_DIR.mkdir(parents=True, exist_ok=True)
    out_5m = OUT_5M_DIR / f"{symbol}.json"
    out_5m.write_text(json.dumps(bars_5m, indent=1), encoding="utf-8")
    print(f"  Saved {len(bars_5m)} 5m bars to {out_5m.name}")
    
    # Aggregate into Daily (UTC boundaries)
    bars_daily = _resample(standard_bars, target_minutes=1440)
    OUT_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_daily = OUT_DAILY_DIR / f"{symbol}.json"
    out_daily.write_text(json.dumps(bars_daily, indent=1), encoding="utf-8")
    print(f"  Saved {len(bars_daily)} daily bars to {out_daily.name}")


def _resample(bars: list[dict], target_minutes: int) -> list[dict]:
    resampled = []
    bucket = None
    bucket_key = None

    for bar in bars:
        ts_str = bar["timestamp"]
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        epoch_min = int(ts.timestamp()) // 60
        aligned = (epoch_min // target_minutes) * target_minutes
        key = str(aligned)

        if key != bucket_key:
            if bucket is not None:
                resampled.append(bucket)
            # For daily bars, we want the timestamp to reflect midnight UTC of that day
            if target_minutes >= 1440:
                bucket_ts_str = datetime.fromtimestamp(aligned * 60).strftime("%Y-%m-%dT00:00:00Z")
            else:
                bucket_ts_str = ts_str
                
            bucket = {
                "timestamp": bucket_ts_str,
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
            bucket_key = key
        else:
            bucket["high"] = max(bucket["high"], bar["high"])
            bucket["low"] = min(bucket["low"], bar["low"])
            bucket["close"] = bar["close"]
            bucket["volume"] += bar["volume"]
            # Intraday bars use the last tick timestamp, daily stays at 00:00
            if target_minutes < 1440:
                bucket["timestamp"] = ts_str

    if bucket is not None:
        resampled.append(bucket)

    return resampled


def main():
    if not DUKA_DIR.exists():
        print(f"Dukascopy directory not found: {DUKA_DIR}")
        sys.exit(1)
        
    for p in DUKA_DIR.glob("*.json"):
        convert_file(p)


if __name__ == "__main__":
    main()
