import hashlib
import importlib
import importlib.util
import json
import math
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest

DAY = date(2025, 8, 1)
BASE = int(datetime(2025, 8, 1, tzinfo=timezone.utc).timestamp())


def test_diagnostic_module_available():
    assert importlib.util.find_spec("scripts.compare_dukascopy_volume") is not None, (
        "paired volume diagnostic has not been implemented"
    )


@pytest.fixture
def diagnostic(monkeypatch):
    module = importlib.import_module("scripts.compare_dukascopy_volume")

    def offline(*args, **kwargs):
        raise AssertionError("offline tests must not access the network")

    monkeypatch.setattr("urllib.request.urlopen", offline)
    return module


def payload(day=DAY, volumes=(2.125, 0.0), times=None):
    n = len(volumes)
    return {
        "timestamp": int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp())
        * 1000,
        "shift": 60000,
        "multiplier": 0.00001,
        "open": 1.1 if n else None,
        "high": 1.1002 if n else None,
        "low": 1.0998 if n else None,
        "close": 1.1 if n else None,
        "times": ([0] + [1] * (n - 1) if n else []) if times is None else times,
        "opens": [0] * n,
        "highs": [0] * n,
        "lows": [0] * n,
        "closes": [0] * n,
        "volumes": list(volumes),
    }


def tick(offset=0, count=2):
    ts = datetime.fromtimestamp(BASE + offset * 60, timezone.utc)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "o_bid": 1.1, "h_bid": 1.1002, "l_bid": 1.0998, "c_bid": 1.1,
        "o_ask": 1.1001, "h_ask": 1.1003, "l_ask": 1.0999, "c_ask": 1.1001,
        "n": count,
    }


def bars(n=200):
    result = []
    for i in range(n):
        close = 1.1 + 0.01 * math.sin(i / 6)
        result.append({
            "timestamp": datetime.fromtimestamp(BASE + i * 14400, timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": close, "high": close + 0.0005, "low": close - 0.0005,
            "close": close, "volume": i % 5 + 1,
        })
    return result


def records(result):
    trace = result["trace_4h"]
    return [dict(zip(trace["columns"], row)) for row in trace["rows"]]


def test_vendor_decode_preserves_rounded_float_and_zero(diagnostic):
    decoded = diagnostic.validate_vendor_day(payload(), DAY)
    assert decoded[BASE] == (1.1, 1.1002, 1.0998, 1.1, 2.12)
    assert decoded[BASE + 60][-1] == 0.0


@pytest.mark.parametrize("field", ["times", "opens", "highs", "lows", "closes", "volumes"])
def test_unequal_arrays_fail_before_zip_truncation(diagnostic, field):
    raw = payload()
    raw[field].pop()
    with pytest.raises(ValueError, match="equal lengths"):
        diagnostic.validate_vendor_day(raw, DAY)


@pytest.mark.parametrize("times, shift, message", [
    ([0, 0], 60000, "strictly increasing"),
    ([1, -1], 60000, "strictly increasing"),
    ([0, 1440], 60000, "requested UTC date"),
    ([0, 1], 1000, "minute-aligned"),
    ([0, 1], 60000.5, "minute-aligned"),
])
def test_bad_vendor_timestamps_fail(diagnostic, times, shift, message):
    raw = payload(times=times)
    raw["shift"] = shift
    with pytest.raises(ValueError, match=message):
        diagnostic.validate_vendor_day(raw, DAY)


@pytest.mark.parametrize("field, value", [
    ("volumes", [-1, 0]), ("volumes", [float("nan"), 0]),
    ("closes", [float("inf"), 0]), ("open", "1.1"),
    ("high", 1.0), ("shift", 0), ("multiplier", -1),
])
def test_bad_vendor_numbers_and_ohlc_fail(diagnostic, field, value):
    raw = payload()
    raw[field] = value
    with pytest.raises(ValueError):
        diagnostic.validate_vendor_day(raw, DAY)


@pytest.mark.parametrize("raw", [[], {}, {"times": []}, {"error": "unavailable"}])
def test_endpoint_shape_errors_are_clear(diagnostic, raw):
    with pytest.raises(ValueError, match="payload|array"):
        diagnostic.validate_vendor_day(raw, DAY)


def test_explicit_empty_day_is_distinct_from_bad_shape(diagnostic):
    assert diagnostic.validate_vendor_day(payload(volumes=()), DAY) == {}
    raw = payload(volumes=())
    raw["open"] = 1.1
    with pytest.raises(ValueError, match="empty"):
        diagnostic.validate_vendor_day(raw, DAY)


@pytest.mark.parametrize("count", [0, -1, 1.5, True, float("nan"), float("inf"), "2"])
def test_tick_counts_must_be_finite_positive_integers(diagnostic, count):
    with pytest.raises(ValueError, match="tick count"):
        diagnostic.validate_tick_rows([tick(count=count)])


@pytest.mark.parametrize("rows", [[tick(), tick()], [tick(1), tick()], [tick() | {
    "timestamp": "2025-08-01T00:00:01Z"
}]])
def test_tick_timestamps_sorted_unique_and_aligned(diagnostic, rows):
    with pytest.raises(ValueError, match="timestamp|minute-aligned|strictly increasing"):
        diagnostic.validate_tick_rows(rows)


def test_common_minute_generators_change_only_n_and_do_not_mutate(diagnostic):
    ticks = [tick(0, 2), tick(1, 4), tick(240, 6)]
    original = deepcopy(ticks)
    vendor = {BASE + 60: (9, 10, 8, 9, 0.0), BASE + 120: (9, 10, 8, 9, 999),
              BASE + 14400: (9, 10, 8, 9, 3.25)}
    left = list(diagnostic.paired_rows(ticks, vendor, vendor_volume=False))
    right = list(diagnostic.paired_rows(ticks, vendor, vendor_volume=True))
    assert left == ticks[1:]
    assert right == [ticks[1] | {"n": 0.0}, ticks[2] | {"n": 3.25}]
    assert ticks == original
    report = diagnostic.compare_symbol(ticks, vendor)
    coverage = report["minute_coverage"]
    assert (coverage["shared"], coverage["tick_only"], coverage["vendor_only"]) == (2, 1, 1)
    assert coverage["tick_lost_fraction"] == pytest.approx(1 / 3)
    assert coverage["vendor_lost_fraction"] == pytest.approx(1 / 3)
    assert report["native_bid_ohlc"]["mismatched_minutes"] == 2
    assert report["prices_and_timestamps_equal_4h"] is True
    assert report["volumes"]["4h"]["tick_sum"] == 10
    assert report["volumes"]["4h"]["vendor_sum"] == 3.25
    assert [r["vendor_volume"] for r in records(report)] == [0.0, 3.25]


def test_volume_statistics_and_undefined_correlations(diagnostic):
    result = diagnostic.volume_statistics([1, 2, 4], [2, 4, 8])
    assert result["pearson"] == pytest.approx(1)
    assert result["spearman"] == pytest.approx(1)
    assert result["vendor_per_tick"] == dict.fromkeys(["min", "p05", "median", "p95", "max"], 2)
    zero = diagnostic.volume_statistics([1, 1, 1], [0, 0, 0])
    assert zero["pearson"] is None and zero["spearman"] is None
    assert zero["vendor_zero_count"] == 3
    assert json.loads(json.dumps(zero, allow_nan=False)) == zero


def test_nonproportional_weights_change_known_vwap_and_zero_falls_back(diagnostic):
    assert diagnostic.rolling_vwap([10, 20], [1, 1]) == 15
    assert diagnostic.rolling_vwap([10, 20], [1, 3]) == 17.5
    assert diagnostic.rolling_vwap([10, 20], [0, 0]) == 15


def test_exact_scaling_preserves_vwap_signals_positions_and_warmup(diagnostic):
    left = bars()
    right = [b | {"volume": b["volume"] * 2} for b in left]
    result = diagnostic.compare_signals(left, right)
    trace = records(result)
    post = trace[120:]
    summary = result["sensitivity"]
    assert summary["postwarmup_bars"] == len(left) - 120
    assert trace[119]["tick_vwap"] is None and trace[120]["tick_vwap"] is not None
    assert all(r["tick_vwap"] == r["vendor_vwap"] for r in post)
    assert summary["ema_side_disagreement"]["count"] == 0
    assert summary["signal_disagreement"]["count"] == 0
    assert summary["position_disagreement"]["count"] == 0
    assert summary["signal_disagreement"]["union_signal_bars"] > 0
    assert any(r["tick_signal"] and r["tick_position"] == 0 for r in post)
    assert sum(m["denominator"] for m in summary["monthly_positions"].values()) == len(post)
    assert sum(m["union_active_bars"] for m in summary["monthly_positions"].values()) == (
        summary["position_disagreement"]["union_active_bars"]
    )


def test_trace_matches_independent_strategy_including_stop_exits(diagnostic):
    from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP

    left = bars(260)
    right = [b | {"volume": 0.0} for b in left]
    result = diagnostic.compare_signals(left, right)
    trace = records(result)
    for arm, source in (("tick", left), ("vendor", right)):
        strategy = TraderDevEMA9VWAP(**diagnostic.PARAMS)
        stale_seen = False
        for i, (bar, row) in enumerate(zip(source, trace)):
            assert row[f"{arm}_signal"] == strategy.update_bar(bar)
            assert row[f"{arm}_position"] == strategy.position
            if i >= 120:
                window = source[i - 119:i + 1]
                prices = [b["close"] for b in window]
                expected = diagnostic.rolling_vwap(prices, [b["volume"] for b in window])
                assert row[f"{arm}_vwap"] == pytest.approx(expected)
                assert row["ema"] == strategy._ema(prices[-9:], 9)
                stale_seen |= strategy._prev_vwap != expected
        assert stale_seen, "fixture must exercise stops that leave _prev_vwap stale"
    post = trace[120:]
    expected = sum(r["tick_position"] != r["vendor_position"] for r in post)
    assert result["sensitivity"]["position_disagreement"]["count"] == expected
    assert result["sensitivity"]["vwap_difference_pips"]["max"] > 0
    json.dumps(result, allow_nan=False)


def test_short_sample_has_explicit_zero_denominators(diagnostic):
    result = diagnostic.compare_signals(bars(120), bars(120))
    assert result["sensitivity"]["postwarmup_bars"] == 0
    assert result["sensitivity"]["position_disagreement"]["fraction"] is None
    assert result["sensitivity"]["vwap_difference_pips"]["median"] is None
    json.dumps(result, allow_nan=False)


def test_price_or_timestamp_differences_cannot_enter_signal_comparison(diagnostic):
    left = bars(2)
    with pytest.raises(AssertionError, match="price|timestamp"):
        diagnostic.compare_signals(left, [left[0] | {"close": 9}, left[1]])


def test_cache_is_hashed_reused_and_revalidated(diagnostic, tmp_path, monkeypatch):
    calls = []

    def fetch(code, side, day):
        calls.append((code, side, day))
        return payload(day)

    monkeypatch.setattr(diagnostic, "fetch_day", fetch)
    first, manifest = diagnostic.load_vendor_day("EURUSD", DAY, tmp_path)
    path = tmp_path / "EURUSD" / f"{DAY}.json"
    assert manifest["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest["source"] == "fetched"
    second, reused = diagnostic.load_vendor_day("EURUSD", DAY, tmp_path)
    assert first == second and reused["source"] == "cache"
    assert calls == [("EUR-USD", "BID", DAY)]
    broken = payload()
    broken["opens"].pop()
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="equal lengths"):
        diagnostic.load_vendor_day("EURUSD", DAY, tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize("empty", [True, False])
def test_empty_and_failed_days_abort_visibly(diagnostic, tmp_path, monkeypatch, capsys, empty):
    def fetch(*args):
        if empty:
            return payload(volumes=())
        raise RuntimeError("unavailable")

    monkeypatch.setattr(diagnostic, "fetch_day", fetch)
    audit = {}
    with pytest.raises(RuntimeError, match="2025-08-01"):
        diagnostic.collect_vendor("EURUSD", [DAY], tmp_path, 1, audit)
    assert audit["failures"][0]["day"] == DAY.isoformat()
    assert audit["empty_days"] == ([DAY.isoformat()] if empty else [])
    assert "2025-08-01" in capsys.readouterr().err


def test_end_to_end_report_is_offline_nonqualifying_and_inputs_immutable(
    diagnostic, tmp_path, monkeypatch
):
    source = tmp_path / "ticks"
    source.mkdir()
    path = source / "EURUSD.json"
    path.write_text(json.dumps([tick(), tick(1)]), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(diagnostic, "TICK_DIR", source)
    monkeypatch.setattr(diagnostic, "fetch_day", lambda code, side, day: payload(day))
    output = tmp_path / "diagnostic.json"
    report = diagnostic.run_diagnostic(tmp_path / "cache", output, ["EURUSD"], 1)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == report and report["can_qualify"] is False
    assert report["diagnostic_only"] is True and report["status"] == "complete"
    assert report["warmup"]["first_decision_index"] == 120
    assert report["symbols"]["EURUSD"]["acquisition"]["days_fetched"] == 1
    assert report["provenance"]["tick_files"]["EURUSD"]["sha256"] == (
        hashlib.sha256(original).hexdigest()
    )
    assert {"script", "strategy", "resampler", "fetch_decoder"} <= (
        report["provenance"]["code"].keys()
    )
    assert path.read_bytes() == original
    json.dumps(report, allow_nan=False)
    with pytest.raises(FileExistsError):
        diagnostic.run_diagnostic(tmp_path / "cache", output, ["EURUSD"], 1)


def test_failed_run_writes_failure_diagnostic_and_propagates(diagnostic, tmp_path, monkeypatch):
    source = tmp_path / "ticks"
    source.mkdir()
    (source / "EURUSD.json").write_text(json.dumps([tick()]), encoding="utf-8")
    monkeypatch.setattr(diagnostic, "TICK_DIR", source)
    monkeypatch.setattr(diagnostic, "fetch_day", lambda *args: {"error": "bad endpoint"})
    output = tmp_path / "failed.json"
    with pytest.raises(RuntimeError):
        diagnostic.run_diagnostic(tmp_path / "cache", output, ["EURUSD"], 1)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed" and report["can_qualify"] is False
    assert report["symbols"]["EURUSD"]["acquisition"]["failures"]


@pytest.mark.parametrize("workers", [0, 5])
def test_worker_limit_rejected_before_requests(diagnostic, tmp_path, workers):
    with pytest.raises(ValueError, match="workers"):
        diagnostic.collect_vendor("EURUSD", [DAY], tmp_path, workers, {})


def test_bounded_batches_and_progress(diagnostic, tmp_path, monkeypatch, capsys):
    pending = 0
    maximum = 0

    class Pool:
        def __init__(self, max_workers):
            assert max_workers == 4

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def submit(self, fn, *args):
            nonlocal pending, maximum
            pending += 1
            maximum = max(maximum, pending)

            class Future:
                def result(self):
                    nonlocal pending
                    pending -= 1
                    return fn(*args)

            return Future()

    monkeypatch.setattr(diagnostic, "ThreadPoolExecutor", Pool)
    monkeypatch.setattr(diagnostic, "fetch_day", lambda code, side, day: payload(day))
    days = [DAY + timedelta(days=i) for i in range(27)]
    audit = {}
    result = diagnostic.collect_vendor("EURUSD", days, tmp_path, 4, audit)
    assert len(result) == 54 and maximum == 4
    assert audit["days_fetched"] == 27
    assert "25/27" in capsys.readouterr().out
