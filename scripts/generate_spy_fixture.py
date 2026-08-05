"""Generate synthetic SPY daily OHLCV fixture (2020-01-02 to 2024-12-31)."""

import csv
from pathlib import Path


def generate_spy_bars() -> list[dict]:
    """Generate approximate SPY daily bars covering major market regimes.

    Regimes:
    2020-01-02 to 2020-02-19: ~322 to ~338 (all-time highs, pre-COVID)
    2020-02-20 to 2020-03-23: ~338 to ~223 (COVID crash, -34%)
    2020-03-24 to 2020-12-31: ~223 to ~370 (V-shaped recovery, +66%)
    2021-01-04 to 2021-12-31: ~370 to ~470 (steady uptrend, +27%)
    2022-01-03 to 2022-10-12: ~470 to ~360 (bear market, -23%)
    2022-10-13 to 2022-12-30: ~360 to ~380 (partial recovery)
    2023-01-03 to 2023-12-29: ~380 to ~470 (recovery year, +24%)
    2024-01-02 to 2024-12-31: ~470 to ~585 (uptrend, +24%)
    """
    regimes: list[tuple[str, str, float, float]] = [
        ("2020-01-02", "2020-02-19", 322.0, 338.0),
        ("2020-02-20", "2020-03-23", 338.0, 223.0),  # crash
        ("2020-03-24", "2020-12-31", 223.0, 370.0),  # recovery
        ("2021-01-04", "2021-12-31", 370.0, 470.0),
        ("2022-01-03", "2022-10-12", 470.0, 360.0),  # bear
        ("2022-10-13", "2022-12-30", 360.0, 380.0),
        ("2023-01-03", "2023-12-29", 380.0, 470.0),
        ("2024-01-02", "2024-12-31", 470.0, 585.0),
    ]

    from datetime import datetime, timedelta

    bars: list[dict] = []
    volume = 80_000_000  # starting volume

    for start_str, end_str, start_price, end_price in regimes:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
        days = (end - start).days + 1

        for i in range(days):
            dt = start + timedelta(days=i)
            if dt.weekday() >= 5:
                continue  # skip weekends
            progress = i / max(days - 1, 1)
            # S-curve interpolation for more realistic price paths
            t = progress
            smooth = t * t * (3 - 2 * t)  # smoothstep
            close = start_price + (end_price - start_price) * smooth

            # Add daily noise
            import random
            noise_pct = random.gauss(0, 0.005)  # 0.5% daily noise
            noise_pts = close * noise_pct
            close = round(close + noise_pts, 2)

            # Generate OHLC from close
            daily_range = close * 0.015  # 1.5% typical daily range
            open_ = round(close + random.gauss(0, daily_range * 0.3), 2)
            high_ = round(max(open_, close) + abs(random.gauss(0, daily_range * 0.4)), 2)
            low_ = round(min(open_, close) - abs(random.gauss(0, daily_range * 0.4)), 2)

            # Volume varies
            import random
            volume = int(volume * (1 + random.gauss(0, 0.2)))
            volume = max(volume, 10_000_000)
            volume = min(volume, 500_000_000)

            bars.append({
                "symbol": "SPY",
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
    bars = generate_spy_bars()
    path = Path("tests/fixtures/market/spy_2020_2024.csv")
    write_csv(bars, path)
    print(f"Date range: {bars[0]['date']} to {bars[-1]['date']}")
