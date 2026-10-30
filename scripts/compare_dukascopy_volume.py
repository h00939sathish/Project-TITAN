"""Paired input/signal diagnostic on the exhausted tuning year; never qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.pull_dukascopy_jetta import decode_day, fetch_day  # noqa: E402
from titan.research.wf_v2 import months_between, resample_window, spearman  # noqa: E402
from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP  # noqa: E402

TICK_DIR = ROOT / "research" / "dukascopy_1m_ba"
START, END = date(2025, 8, 1), date(2026, 7, 31)
SYMBOLS = {"EURUSD": "EUR-USD", "GBPUSD": "GBP-USD"}
PARAMS = {"ema_period": 9, "vwap_period": 120, "atr_period": 14, "trail_mult": 2.0}
WARMUP = 120
PIP = 0.0001
OHLC = ("open", "high", "low", "close")
BID = ("o_bid", "h_bid", "l_bid", "c_bid")
ARRAYS = ("times", "opens", "highs", "lows", "closes", "volumes")


class DayRequestError(RuntimeError):
    pass


def finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: expected finite numeric value")
    try:
        if math.isfinite(value):
            return float(value)
    except OverflowError:
        pass
    raise ValueError(f"{label}: expected finite numeric value")


def validate_ohlc(values: Iterable[float], label: str) -> None:
    o, h, low, c = [finite_number(v, label) for v in values]
    if low > min(o, c, h) + 1e-9 or h < max(o, c, low) - 1e-9:
        raise ValueError(f"{label}: invalid OHLC bounds")


def validate_vendor_day(payload: object, day: date) -> dict[int, tuple]:
    if not isinstance(payload, dict):
        raise ValueError("vendor payload must be an object")
    if any(not isinstance(payload.get(k), list) for k in ARRAYS):
        raise ValueError(f"vendor payload requires arrays: {', '.join(ARRAYS)}")
    lengths = {len(payload[k]) for k in ARRAYS}
    if len(lengths) != 1:
        raise ValueError("vendor arrays must have equal lengths")
    n = len(payload["times"])
    if n == 0:
        if any(k not in payload or payload[k] is not None for k in OHLC):
            raise ValueError("empty vendor day requires null OHLC and six empty arrays")
        return {}
    if n > 1440:
        raise ValueError("vendor day exceeds 1440 unique minutes")
    for key in ("timestamp", "shift", "multiplier", *OHLC):
        finite_number(payload.get(key), f"vendor {key}")
    if payload["shift"] <= 0 or payload["multiplier"] <= 0:
        raise ValueError("vendor shift and multiplier must be positive")
    for key in ARRAYS:
        for value in payload[key]:
            finite_number(value, f"vendor {key}")
    if any(v < 0 for v in payload["volumes"]):
        raise ValueError("vendor volumes must be nonnegative")
    start_ms = int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp()) * 1000
    accumulated = 0
    previous = None
    for delta in payload["times"]:
        accumulated += delta
        ms = payload["timestamp"] + accumulated * payload["shift"]
        finite_number(ms, "vendor timestamp")
        if ms % 60000:
            raise ValueError("vendor timestamps must be minute-aligned before decoding")
        if not start_ms <= ms < start_ms + 86400000:
            raise ValueError("vendor timestamp outside requested UTC date")
        if previous is not None and ms <= previous:
            raise ValueError("vendor timestamps must be unique and strictly increasing")
        previous = ms
    decoded = decode_day(payload)
    if len(decoded) != n:
        raise ValueError("vendor decoder changed minute count")
    for ts, values in decoded.items():
        validate_ohlc(values[:4], f"vendor {day} {ts}")
        finite_number(values[4], "decoded vendor volume")
    return decoded


def tick_seconds(row: dict) -> int:
    ts = row.get("timestamp")
    if not isinstance(ts, str):
        raise ValueError("tick timestamp must be a UTC string")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid tick timestamp: {ts}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"tick timestamp must be UTC: {ts}")
    if dt.second or dt.microsecond:
        raise ValueError(f"tick timestamp must be minute-aligned: {ts}")
    if ts != dt.strftime("%Y-%m-%dT%H:%M:%SZ"):
        raise ValueError(f"tick timestamp must use canonical UTC format: {ts}")
    return int(dt.timestamp())


def validate_tick_rows(rows: object) -> None:
    if not isinstance(rows, list) or not rows:
        raise ValueError("tick input must be a nonempty array")
    previous = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("tick row must be an object")
        ts = tick_seconds(row)
        if previous is not None and ts <= previous:
            raise ValueError("tick timestamps must be unique and strictly increasing")
        previous = ts
        count = finite_number(row.get("n"), "tick count")
        if count <= 0 or not count.is_integer():
            raise ValueError("tick count must be a finite positive integer")
        validate_ohlc((row.get(k) for k in BID), f"tick {row['timestamp']}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
            suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, separators=(",", ":"), allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_vendor_day(symbol: str, day: date, cache_dir: Path) -> tuple[dict, dict]:
    path = cache_dir / symbol / f"{day}.json"
    source = "cache" if path.exists() else "fetched"
    if source == "cache":
        raw = path.read_bytes()
        payload = json.loads(raw)
    else:
        try:
            payload = fetch_day(SYMBOLS[symbol], "BID", day)
        except Exception as exc:
            raise DayRequestError(f"{symbol} {day}: request failed: {exc}") from exc
    decoded = validate_vendor_day(payload, day)
    if source == "fetched":
        write_json(path, payload)
        raw = path.read_bytes()
    return decoded, {
        "day": day.isoformat(), "path": str(path.resolve()), "source": source,
        "sha256": hashlib.sha256(raw).hexdigest(), "minutes": len(decoded),
        "empty": not decoded,
    }


def collect_vendor(
    symbol: str, days: list[date], cache_dir: Path, workers: int, audit: dict,
) -> dict[int, tuple]:
    if not 1 <= workers <= 4:
        raise ValueError("workers must be between 1 and 4")
    audit.update(requested_days=len(days), completed_days=0, days_fetched=0, cache_reused=0,
                 empty_days=[], failures=[], failed_requests=0, manifest=[])
    started = time.perf_counter()
    vendor = {}
    remaining = iter(days)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while batch := list(islice(remaining, workers)):
                futures = [(day, pool.submit(load_vendor_day, symbol, day, cache_dir))
                           for day in batch]
                cause = None
                for day, future in futures:
                    try:
                        decoded, manifest = future.result()
                        audit["manifest"].append(manifest)
                        audit["days_fetched" if manifest["source"] == "fetched"
                              else "cache_reused"] += 1
                        if not decoded:
                            audit["empty_days"].append(day.isoformat())
                            raise ValueError("empty vendor day on a date with tick data")
                        vendor.update(decoded)
                    except Exception as exc:
                        cause = exc
                        audit["failures"].append({
                            "day": day.isoformat(), "type": type(exc).__name__, "error": str(exc),
                        })
                        audit["failed_requests"] += isinstance(exc, DayRequestError)
                        print(f"{symbol} {day}: FAILED {exc}", file=sys.stderr, flush=True)
                    audit["completed_days"] += 1
                    done = audit["completed_days"]
                    if done % 25 == 0 or done == len(days):
                        print(f"{symbol}: {done}/{len(days)} days; "
                              f"fetched={audit['days_fetched']} cache={audit['cache_reused']} "
                              f"failures={len(audit['failures'])}", flush=True)
                if cause is not None:
                    failed = ", ".join(f["day"] for f in audit["failures"])
                    message = f"{symbol}: unavailable or malformed days: {failed}"
                    raise RuntimeError(message) from cause
    finally:
        audit["seconds"] = time.perf_counter() - started
        audit["unprocessed_days"] = len(days) - audit["completed_days"]
    return vendor


def paired_rows(ticks: list[dict], vendor: dict, *, vendor_volume: bool) -> Iterator[dict]:
    for row in ticks:
        ts = tick_seconds(row)
        if ts in vendor:
            yield row | {"n": vendor[ts][4] if vendor_volume else row["n"]}


def fraction(count: int, denominator: int) -> float | None:
    return count / denominator if denominator else None


def quantiles(values: list[float]) -> dict:
    ordered = sorted(values)

    def percentile(p: float) -> float | None:
        if not ordered:
            return None
        index = (len(ordered) - 1) * p
        lo = int(index)
        hi = min(lo + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)

    return {key: percentile(p) for key, p in
            (("min", 0), ("p05", 0.05), ("median", 0.5), ("p95", 0.95), ("max", 1))}


def volume_statistics(tick: list[float], vendor: list[float]) -> dict:
    if len(tick) != len(vendor):
        raise ValueError("volume statistics require paired equal-length samples")
    try:
        pearson = statistics.correlation(tick, vendor)
    except statistics.StatisticsError:
        pearson = None
    rank = spearman(tick, vendor)
    return {
        "pairs": len(tick),
        "pearson": pearson if pearson is not None and math.isfinite(pearson) else None,
        "spearman": rank if rank is not None and math.isfinite(rank) else None,
        "vendor_per_tick": quantiles([v / t for t, v in zip(tick, vendor) if t > 0]),
        "ratio_denominator": sum(t > 0 for t in tick),
        "tick_zero_count": tick.count(0), "vendor_zero_count": vendor.count(0),
        "tick_sum": sum(tick), "vendor_sum": sum(vendor),
    }


def rolling_vwap(closes: list[float], volumes: list[float]) -> float:
    total = sum(volumes)
    return (sum(p * v for p, v in zip(closes, volumes)) / total if total > 0
            else sum(closes) / len(closes))


def position_summary(pairs: list[tuple[int, int]]) -> dict:
    count = sum(a != b for a, b in pairs)
    active = sum(a != 0 or b != 0 for a, b in pairs)
    return {"count": count, "denominator": len(pairs), "fraction": fraction(count, len(pairs)),
            "union_active_bars": active, "union_active_fraction": fraction(count, active)}


def compare_signals(tick_bars: list[dict], vendor_bars: list[dict]) -> dict:
    if len(tick_bars) != len(vendor_bars) or any(
        any(a[k] != b[k] for k in ("timestamp", *OHLC))
        for a, b in zip(tick_bars, vendor_bars)
    ):
        raise AssertionError("paired 4h prices and timestamps differ")
    tick_strategy = TraderDevEMA9VWAP(**PARAMS)
    vendor_strategy = TraderDevEMA9VWAP(**PARAMS)
    columns = ["timestamp", "bid_close", "tick_volume", "vendor_volume", "ema", "tick_vwap",
               "vendor_vwap", "tick_signal", "vendor_signal", "tick_position", "vendor_position"]
    trace, differences, positions = [], [], []
    monthly = {b["timestamp"][:7]: [] for b in tick_bars}
    signal_count = signal_union = side_count = 0
    mismatch_times = []
    for i, (a, b) in enumerate(zip(tick_bars, vendor_bars)):
        tick_signal = tick_strategy.update_bar(a)
        vendor_signal = vendor_strategy.update_bar(b)
        ema = tick_vwap = vendor_vwap = None
        if i >= WARMUP:
            closes = [bar["close"] for bar in tick_bars[i - WARMUP + 1:i + 1]]
            tick_vols = [bar["volume"] for bar in tick_bars[i - WARMUP + 1:i + 1]]
            vendor_vols = [bar["volume"] for bar in vendor_bars[i - WARMUP + 1:i + 1]]
            tick_vwap = rolling_vwap(closes, tick_vols)
            vendor_vwap = rolling_vwap(closes, vendor_vols)
            ema = tick_strategy._ema(closes[-PARAMS["ema_period"]:], PARAMS["ema_period"])
            differences.append((vendor_vwap - tick_vwap) / PIP)
            side_count += ((ema > tick_vwap) - (ema < tick_vwap)
                           != (ema > vendor_vwap) - (ema < vendor_vwap))
            signal_count += tick_signal != vendor_signal
            signal_union += tick_signal is not None or vendor_signal is not None
            pair = (tick_strategy.position, vendor_strategy.position)
            positions.append(pair)
            monthly[a["timestamp"][:7]].append(pair)
            if (pair[0] != pair[1] or tick_signal != vendor_signal) and len(mismatch_times) < 10:
                mismatch_times.append(a["timestamp"])
        trace.append([a["timestamp"], a["close"], a["volume"], b["volume"], ema,
                      tick_vwap, vendor_vwap, tick_signal, vendor_signal,
                      tick_strategy.position, vendor_strategy.position])
    n = len(differences)
    return {
        "prices_and_timestamps_equal_4h": True,
        "sensitivity": {
            "bars_4h": len(tick_bars), "warmup_bars_excluded": min(WARMUP, len(tick_bars)),
            "postwarmup_bars": n,
            "vwap_difference_pips": quantiles([abs(d) for d in differences]) | {
                "denominator": n, "signed_mean": statistics.fmean(differences) if n else None,
                "sign": "vendor minus tick; quantiles are absolute",
            },
            "ema_side_disagreement": {"count": side_count, "denominator": n,
                                      "fraction": fraction(side_count, n)},
            "signal_disagreement": {
                "count": signal_count, "denominator": n, "fraction": fraction(signal_count, n),
                "union_signal_bars": signal_union,
                "union_signal_fraction": fraction(signal_count, signal_union),
            },
            "position_disagreement": position_summary(positions),
            "monthly_positions": {month: position_summary(pairs)
                                  for month, pairs in sorted(monthly.items())},
            "first_signal_or_position_mismatch_timestamps": mismatch_times,
        },
        "trace_4h": {"columns": columns, "rows": trace},
    }


def compare_symbol(ticks: list[dict], vendor: dict) -> dict:
    tick_set = {tick_seconds(row) for row in ticks}
    vendor_set = set(vendor)
    shared = tick_set & vendor_set
    if not shared:
        raise ValueError("no common minutes for paired construction")
    tick_only, vendor_only = len(tick_set - vendor_set), len(vendor_set - tick_set)
    coverage = {
        "tick_minutes": len(tick_set), "vendor_minutes": len(vendor_set),
        "shared": len(shared), "tick_only": tick_only, "vendor_only": vendor_only,
        "union_minutes": len(tick_set | vendor_set),
        "shared_of_tick_fraction": fraction(len(shared), len(tick_set)),
        "shared_of_vendor_fraction": fraction(len(shared), len(vendor_set)),
        "tick_lost_fraction": fraction(tick_only, len(tick_set)),
        "vendor_lost_fraction": fraction(vendor_only, len(vendor_set)),
        "tick_lost_percent": 100 * tick_only / len(tick_set),
        "vendor_lost_percent": 100 * vendor_only / len(vendor_set),
    }
    mismatch_count = 0
    max_pips = 0.0
    tick_volumes, vendor_volumes = [], []
    for row in ticks:
        ts = tick_seconds(row)
        if ts not in shared:
            continue
        native = vendor[ts]
        differences = [abs(row[k] - price) for k, price in zip(BID, native[:4])]
        mismatch_count += any(d > 1e-9 for d in differences)
        max_pips = max(max_pips, max(differences) / PIP)
        tick_volumes.append(row["n"])
        vendor_volumes.append(native[4])
    months = months_between(START.strftime("%Y-%m"), END.strftime("%Y-%m"))
    tick_bars, _ = resample_window(paired_rows(ticks, vendor, vendor_volume=False), months, 240)
    vendor_bars, _ = resample_window(paired_rows(ticks, vendor, vendor_volume=True), months, 240)
    result = compare_signals(tick_bars, vendor_bars)
    result.update(
        minute_coverage=coverage,
        native_bid_ohlc={"matched_minutes": len(shared), "mismatched_minutes": mismatch_count,
                         "max_pips": max_pips, "absolute_price_tolerance": 1e-9},
        volumes={"1m": volume_statistics(tick_volumes, vendor_volumes),
                 "4h": volume_statistics([b["volume"] for b in tick_bars],
                                         [b["volume"] for b in vendor_bars])},
    )
    return result


def run_diagnostic(cache_dir: Path, output: Path, symbols: list[str], workers: int) -> dict:
    cache_dir, output = cache_dir.resolve(), output.resolve()
    if not 1 <= workers <= 4:
        raise ValueError("workers must be between 1 and 4")
    if not symbols or any(s not in SYMBOLS for s in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("symbols must be unique EURUSD/GBPUSD choices")
    if cache_dir.is_relative_to(ROOT) or output.is_relative_to(ROOT):
        raise ValueError("cache and diagnostic output must be outside the repository")
    if output.is_relative_to(cache_dir) or output.suffix.lower() != ".json":
        raise ValueError("output must be a separate JSON file outside the raw cache")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing diagnostic: {output}")
    started = time.perf_counter()
    code_paths = {
        "script": Path(__file__),
        "strategy": ROOT / "src/titan/strategies/traderdev_ema9vwap.py",
        "resampler": ROOT / "src/titan/research/wf_v2.py",
        "fetch_decoder": ROOT / "scripts/pull_dukascopy_jetta.py",
    }
    report = {
        "schema_version": 1, "can_qualify": False, "diagnostic_only": True, "status": "running",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": START.isoformat(), "end": END.isoformat(), "timezone": "UTC",
                   "classification": "exhausted old tuning year, NOT new OOS"},
        "params": PARAMS.copy(), "timeframe_minutes": 240, "pip_size": PIP,
        "warmup": {"bars": WARMUP, "first_decision_index": WARMUP,
                   "rule": "source checks history length BEFORE append; compare indices >=120"},
        "method": {
            "calendar": "distinct dates present in each tick input within the fixed window",
            "pairing": "inner join on UTC minute; BOTH arms use tick BID OHLC; only n changes",
            "tick_volume": "n is the count of accepted ticks from original aggregate_1m",
            "vendor_volume": "native BID candle volume; decode_day round(volume, 2); "
                             "float, not count",
            "resampling": "wf_v2.resample_window(common-minute generators, months, 240), sums n",
            "indicators": "last120 close-weighted VWAP, all-zero volume falls back to SMA; "
                          "EMA uses source _ema(last9,9); never read _prev_vwap",
            "signals": "independent TraderDevEMA9VWAP.update_bar instances; position property "
                       "after each bar, including flat exits; no fills or performance calculation",
            "ema_side": "exact three-way sign(EMA - instantaneous VWAP), no threshold",
            "quantiles": "linear interpolation at (n-1)*p; undefined statistics are null",
            "cache": "validated raw columnar JSON; per-day SHA256 manifests; max4 bounded batches",
            "failure": "empty vendor day with tick data or malformed/unavailable day aborts; "
                       "failure report is incomplete and cannot stand in for a comparison",
        },
        "exclusions": ["unmatched minutes from both arms, never filled", "no zero-volume drops",
                       "first120 4h bars excluded only from sensitivity summaries",
                       "dates absent from tick inputs are not requested",
                       "no returns, Sharpe, evaluation, materiality verdict, or promotion"],
        "provenance": {"code": {k: {"path": str(p.resolve()), "sha256": sha256(p)}
                                 for k, p in code_paths.items()}, "tick_files": {}},
        "workers": workers, "cache_dir": str(cache_dir), "symbols": {}, "timings_seconds": {},
    }
    try:
        for symbol in symbols:
            symbol_started = time.perf_counter()
            path = TICK_DIR / f"{symbol}.json"
            fingerprint = sha256(path)
            report["provenance"]["tick_files"][symbol] = {
                "path": str(path.resolve()), "sha256": fingerprint,
            }
            with path.open(encoding="utf-8") as stream:
                all_ticks = json.load(stream)
            validate_tick_rows(all_ticks)
            ticks = [row for row in all_ticks
                     if START.isoformat() <= row["timestamp"][:10] <= END.isoformat()]
            if not ticks:
                raise ValueError(f"{symbol}: no tick minutes inside fixed window")
            days = sorted({date.fromisoformat(row["timestamp"][:10]) for row in ticks})
            day_set = set(days)
            result = {"input_rows": len(all_ticks), "window_rows": len(ticks),
                      "outside_window_rows_excluded": len(all_ticks) - len(ticks),
                      "tick_days": len(days), "acquisition": {},
                      "dates_without_ticks_not_requested": [
                          d.isoformat() for i in range((END - START).days + 1)
                          if (d := START + timedelta(days=i)) not in day_set]}
            report["symbols"][symbol] = result
            del all_ticks
            vendor = collect_vendor(symbol, days, cache_dir, workers, result["acquisition"])
            analysis_started = time.perf_counter()
            result.update(compare_symbol(ticks, vendor))
            if sha256(path) != fingerprint:
                raise ValueError(f"{symbol}: tick input changed during diagnostic")
            result["analysis_seconds"] = time.perf_counter() - analysis_started
            result["total_seconds"] = time.perf_counter() - symbol_started
        report["status"] = "complete"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["timings_seconds"]["total"] = time.perf_counter() - started
        write_json(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", required=True, type=Path,
                        help="raw daily cache directory outside the repository")
    parser.add_argument("--output", required=True, type=Path,
                        help="new separate diagnostic JSON outside the repository and raw cache")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--symbol", action="append", choices=SYMBOLS)
    args = parser.parse_args(argv)
    try:
        run_diagnostic(args.cache_dir, args.output, args.symbol or list(SYMBOLS), args.workers)
    except Exception as exc:
        print(f"volume diagnostic FAILED: {exc}", file=sys.stderr, flush=True)
        return 1
    print(f"Diagnostic only (cannot qualify): {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
