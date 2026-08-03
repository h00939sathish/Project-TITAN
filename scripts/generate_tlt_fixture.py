"""Generate synthetic TLT daily OHLCV fixture (2020-01-02 to 2024-12-31).

TLT (iShares 20+ Year Treasury Bond ETF) has different volatility
dynamics than equities — bonds had a brutal 2022 bear market.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_tlt_bars() -> list[dict]:
    """Generate approximate TLT daily bars covering major bond regimes.

    TLT regimes (different from equities — bonds had a brutal 2022 bear market):
    2020-01-02 to 2020-03-09: ~140 to ~165 (flight to safety, COVID panic)
    2020-03-10 to 2020-08-03: ~165 to ~150 (recovery, rates stabilize)
    2020-08-04 to 2021-12-31: ~150 to ~140 (slow grind lower, rates normalize)
    2022-01-03 to 2022-10-24: ~140 to ~90 (rate hiking cycle, -35% crash)
    2022-10-25 to 2023-12-29: ~90 to ~100 (partial recovery)
    2024-01-02 to 2024-12-31: ~100 to ~95 (choppy, rates stay high)
    """
    regimes: list[tuple[str, str, float, float]] = [
        ("2020-01-02", "2020-03-09", 140.0, 165.0),
        ("2020-03-10", "2020-08-03", 165.0, 150.0),
        ("2020-08-04", "2021-12-31", 150.0, 140.0),
        ("2022-01-03", "2022-10-24", 140.0, 90.0),
        ("2022-10-25", "2023-12-29", 90.0, 100.0),
        ("2024-01-02", "2024-12-31", 100.0, 95.0),
    ]

    bars: list[dict] = []
    volume = 15_000_000
    random.seed(42)

    for start_str, end_str, start_price, end_price in regimes:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
        days = (end - start).days + 1

        for i in range(days):
            dt = start + timedelta(days=i)
            if dt.weekday() >= 5:
                continue
            progress = i / max(days - 1, 1)
            t = progress
            smooth = t * t * (3 - 2 * t)
            close = start_price + (end_price - start_price) * smooth

            noise_pct = random.gauss(0, 0.010)
            noise_pts = close * noise_pct
            close = round(close + noise_pts, 2)

            daily_range = close * 0.025
            open_ = round(close + random.gauss(0, daily_range * 0.3), 2)
            high_ = round(max(open_, close) + abs(random.gauss(0, daily_range * 0.4)), 2)
            low_ = round(min(open_, close) - abs(random.gauss(0, daily_range * 0.4)), 2)

            volume = int(volume * (1 + random.gauss(0, 0.2)))
            volume = max(volume, 1_000_000)
            volume = min(volume, 100_000_000)

            bars.append({
                "symbol": "TLT",
                "date": dt.strftime("%Y-%m-%d"),
                "open": f"{open_:.2f}",
                "high": f"{high_:.2f}",
                "low": f"{low_:.2f}",
                "close": f"{close:.2f}",
                "volume": str(volume),
            })

    return bars


def write_csv(bars: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(bars)
    print(f"Wrote {len(bars)} bars to {path}")


if __name__ == "__main__":
    bars = generate_tlt_bars()
    path = Path("tests/fixtures/market/tlt_2020_2024.csv")
    write_csv(bars, path)
    print(f"Date range: {bars[0]['date']} to {bars[-1]['date']}")
