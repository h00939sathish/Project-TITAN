"""Generate synthetic QQQ daily OHLCV fixture (2020-01-02 to 2024-12-31).

QQQ has higher volatility and a different price trajectory than SPY.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_qqq_bars() -> list[dict]:
    """Generate approximate QQQ daily bars covering major market regimes.

    QQQ (Nasdaq-100) is more tech-heavy and volatile than SPY.
    Regimes:
    2020-01-02 to 2020-02-19: ~200 to ~225 (pre-COVID highs)
    2020-02-20 to 2020-03-23: ~225 to ~175 (COVID crash, -22% — milder than SPY)
    2020-03-24 to 2020-12-31: ~175 to ~310 (V-shaped recovery, +77%)
    2021-01-04 to 2021-12-31: ~310 to ~400 (strong tech uptrend, +29%)
    2022-01-03 to 2022-10-12: ~400 to ~260 (tech bear, -35% — worse than SPY)
    2022-10-13 to 2022-12-30: ~260 to ~280 (partial recovery)
    2023-01-03 to 2023-12-29: ~280 to ~410 (AI-driven rally, +46%)
    2024-01-02 to 2024-12-31: ~410 to ~520 (continued tech uptrend, +27%)
    """
    regimes: list[tuple[str, str, float, float]] = [
        ("2020-01-02", "2020-02-19", 200.0, 225.0),
        ("2020-02-20", "2020-03-23", 225.0, 175.0),
        ("2020-03-24", "2020-12-31", 175.0, 310.0),
        ("2021-01-04", "2021-12-31", 310.0, 400.0),
        ("2022-01-03", "2022-10-12", 400.0, 260.0),
        ("2022-10-13", "2022-12-30", 260.0, 280.0),
        ("2023-01-03", "2023-12-29", 280.0, 410.0),
        ("2024-01-02", "2024-12-31", 410.0, 520.0),
    ]

    bars: list[dict] = []
    volume = 50_000_000
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

            noise_pct = random.gauss(0, 0.008)
            noise_pts = close * noise_pct
            close = round(close + noise_pts, 2)

            daily_range = close * 0.020
            open_ = round(close + random.gauss(0, daily_range * 0.3), 2)
            high_ = round(max(open_, close) + abs(random.gauss(0, daily_range * 0.4)), 2)
            low_ = round(min(open_, close) - abs(random.gauss(0, daily_range * 0.4)), 2)

            volume = int(volume * (1 + random.gauss(0, 0.2)))
            volume = max(volume, 5_000_000)
            volume = min(volume, 300_000_000)

            bars.append({
                "symbol": "QQQ",
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
    bars = generate_qqq_bars()
    path = Path("tests/fixtures/market/qqq_2020_2024.csv")
    write_csv(bars, path)
    print(f"Date range: {bars[0]['date']} to {bars[-1]['date']}")
