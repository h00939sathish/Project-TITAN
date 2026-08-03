"""Dukascopy bi5 tick-file decoder + 1-min bid/ask bar aggregator.

bi5 format: LZMA-compressed; big-endian 20-byte records:
  int32 seconds-in-hour, int32 ask (24-bit signed packed), int32 bid, int32 askVol, int32 bidVol
Price scale: 10^point (EURUSD/GBPUSD point = 5 -> /1e5).
"""
import lzma
import struct
from datetime import datetime, timedelta, timezone

POINT = 1e5  # 5 decimal places for EURUSD/GBPUSD


def _px(v: int) -> float:
    v = v & 0xFFFFFF
    if v & 0x800000:
        v -= 0x1000000
    return v / POINT


def load_ticks(path: str) -> list[tuple[int, float, float]]:
    """Return [(ms_in_hour, ask, bid), ...] with corrupt records dropped."""
    raw = lzma.decompress(open(path, "rb").read())
    n = len(raw) // 20
    ticks = []
    for i in range(n):
        t, ask, bid, _, _ = struct.unpack_from(">5i", raw, i * 20)
        if not (0 <= t < 3_600_000):  # milliseconds within the hour
            continue
        a, b = _px(ask), _px(bid)
        if a <= 0 or b <= 0 or a < b:
            continue
        ticks.append((t, a, b))
    return ticks


def aggregate_1m(ticks: list[tuple[int, float, float]]) -> list[dict]:
    """Aggregate ticks into 1-minute OHLC bid/ask bars (last-tick close)."""
    bars: dict[int, dict] = {}
    for t, a, b in ticks:
        minute = t // 60_000
        bar = bars.setdefault(minute, {
            "o_ask": a, "h_ask": a, "l_ask": a, "c_ask": a,
            "o_bid": b, "h_bid": b, "l_bid": b, "c_bid": b, "n": 0,
        })
        bar["n"] += 1
        bar["h_ask"] = max(bar["h_ask"], a)
        bar["l_ask"] = min(bar["l_ask"], a)
        bar["c_ask"] = a
        bar["h_bid"] = max(bar["h_bid"], b)
        bar["l_bid"] = min(bar["l_bid"], b)
        bar["c_bid"] = b
    return [{"minute": m, **bars[m]} for m in sorted(bars)]


def day_paths(symbol: str, day: datetime, hours: range | list[int]) -> list[str]:
    """bi5 file paths for one UTC day (month is 0-indexed in the URL)."""
    return [
        f"https://datafeed.dukascopy.com/datafeed/{symbol}/{day.year:04d}/"
        f"{day.month - 1:02d}/{day.day:02d}/{h:02d}h_ticks.bi5"
        for h in hours
    ]


if __name__ == "__main__":
    # Smoke test on the two probed files
    for f in ("/tmp/eurusd_13.bi5", "/tmp/eurusd_14.bi5"):
        ticks = load_ticks(f)
        bars = aggregate_1m(ticks)
        if not ticks:
            print(f"{f}: EMPTY")
            continue
        spans = f"{min(t for t, *_ in ticks)}s..{max(t for t, *_ in ticks)}s"
        mid = sum((a + b) / 2 for _, a, b in ticks) / len(ticks)
        spread = sum((a - b) for _, a, b in ticks) / len(ticks) * 10000
        print(f"{f}: {len(ticks)} ticks ({spans}) | {len(bars)} 1m bars | "
              f"avg mid {mid:.5f} | avg spread {spread:.2f} pips")
