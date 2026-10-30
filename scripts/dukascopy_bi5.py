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


def candle_day_path(symbol: str, day: datetime, side: str) -> str:
    """Path to one UTC day of vendor-aggregated 1m candles ('BID' or 'ASK').

    One request covers a whole day (1440 bars) instead of 24 hourly tick files.
    """
    if side not in ("BID", "ASK"):
        raise ValueError(f"side must be BID or ASK, got {side!r}")
    return (f"https://datafeed.dukascopy.com/datafeed/{symbol}/{day.year:04d}/"
            f"{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5")


def load_candles(path: str) -> dict[int, dict]:
    """Decode a daily 1m candle bi5 into {minute_of_day: OHLCV}.

    24-byte big-endian records: int32 second-of-day, then open/close/low/high
    as int32 scaled by POINT, then float32 volume. Bars with a non-positive
    open are gaps the vendor padded and are dropped.
    """
    raw = lzma.decompress(open(path, "rb").read())
    if len(raw) % 24:
        raise ValueError(f"{path}: {len(raw)} bytes is not a multiple of 24")
    out: dict[int, dict] = {}
    for i in range(len(raw) // 24):
        t, o, c, lo, h, vol = struct.unpack_from(">5if", raw, i * 24)
        if o <= 0 or h <= 0 or lo <= 0 or c <= 0:
            continue
        out[t // 60] = {"open": o / POINT, "high": h / POINT,
                        "low": lo / POINT, "close": c / POINT, "volume": vol}
    return out


def merge_candle_sides(bid: dict[int, dict], ask: dict[int, dict]) -> list[dict]:
    """Join BID/ASK candle dicts into the o_bid/.../c_ask bar schema.

    Only minutes present on both sides are kept, so no bar ever carries a
    half-populated spread. `n` is the vendor's bid volume truncated to int --
    NOT a tick count, so it is not comparable to the `n` the tick path writes.

    The vendor pads every closed minute with a zero-volume bar whose price does
    not move: all 1440 minutes of a Saturday, the Friday tail after the weekly
    close, and the Sunday head before it. The tick path emits no bar for a
    closed hour, so keeping these would give the candle dataset ~29% flat
    zero-return bars that the tick dataset does not have -- enough to halve
    realised volatility and inflate any Sharpe computed on it.
    """
    bars = []
    for m in sorted(set(bid) & set(ask)):
        b, a = bid[m], ask[m]
        if a["close"] < b["close"]:
            continue
        # A minute that really traded has volume; padding never does. Requiring
        # both sides flat as well keeps a genuine minute whose volume rounded
        # to zero but whose price moved.
        if (int(b["volume"]) == 0
                and b["open"] == b["high"] == b["low"] == b["close"]
                and a["open"] == a["high"] == a["low"] == a["close"]):
            continue
        bars.append({
            "minute": m,
            "o_ask": a["open"], "h_ask": a["high"], "l_ask": a["low"], "c_ask": a["close"],
            "o_bid": b["open"], "h_bid": b["high"], "l_bid": b["low"], "c_bid": b["close"],
            "n": int(b["volume"]),
        })
    return bars



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
