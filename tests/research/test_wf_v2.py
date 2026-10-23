"""`titan research run`: WF-v2 eligibility, the screen cost engine, and an end-to-end run."""
import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from titan.cli import cli
from titan.research import wf_v2
from titan.research.classes import HypothesisClass, classify
from titan.research.experiment import Experiment

ROOT = Path(__file__).resolve().parents[2]


def _spec(**overrides) -> dict:
    spec = {
        "strategy_id": "ma-crossover",
        "strategy_params": {"fast": 5, "slow": 20},
        "instruments": ["USDJPY"],
        "timeframe_minutes": 240,
        "window": ["2022-08", "2024-08"],
        "position_mode": "long_short",
        "evidence_record": "research/evidence/EXP-90001.json",
    }
    spec.update(overrides)
    return spec


def _parsed(**overrides) -> wf_v2.WFv2Spec:
    spec, reasons = wf_v2.parse_spec(_spec(**overrides))
    assert reasons == []
    return spec


# ---- registries -----------------------------------------------------------------


def test_real_hypotheses_file_imports():
    experiments, legacy = wf_v2.load_hypotheses(ROOT)
    assert "EXP-00024" in experiments
    assert experiments["EXP-00024"].params["hypothesis_class"] == "volatility"
    assert {"EXP-00002", "EXP-00003", "EXP-00004", "EXP-00005", "EXP-00006"} <= legacy.keys()
    assert not legacy.keys() & experiments.keys()


def test_classify_keeps_economic_rationale():
    exp = Experiment(id="EXP-1", question="q", economic_rationale="a mechanism worth testing",
                     dataset_id="d", features=("f",), target="t")
    tagged = classify(exp, HypothesisClass.TREND)
    assert tagged.economic_rationale == exp.economic_rationale
    assert tagged.params["hypothesis_class"] == "trend"


@pytest.mark.parametrize("exp_id, needle", [
    ("EXP-00024", "sealed negative: EXP-00024_vol_carry.md"),
    ("EXP-00002", "legacy hypothesis with no economic rationale"),
    ("EXP-99999", "unknown hypothesis EXP-99999"),
])
def test_cli_refuses_ineligible_hypotheses(exp_id, needle, tmp_path, monkeypatch):
    from titan.research import queue

    log = tmp_path / "run_log.jsonl"
    monkeypatch.setattr(queue, "RUN_LOG", str(log))
    result = CliRunner().invoke(cli, ["research", "run", exp_id])
    assert result.exit_code == 2, result.output
    assert "REFUSED" in result.output
    record = json.loads(log.read_text(encoding="utf-8"))
    assert (record["exp_id"], record["status"], record["trigger"]) == (exp_id, "REFUSED", "manual")
    assert needle in result.output


def test_sealed_negatives_match_exp_ids_and_whole_strategy_tokens(tmp_path):
    neg = tmp_path / "research" / "neg_results"
    neg.mkdir(parents=True)
    (neg / "EXP-00031_thing.md").write_text("# EXP-31 rejected\nwe persist in version 2\n",
                                            encoding="utf-8")
    (neg / "other.txt").write_text("the rsi screen failed\n", encoding="utf-8")
    assert wf_v2.sealed_negative_matches(tmp_path, "EXP-00031", None) == [
        "EXP-00031_thing.md (seals EXP-00031)"]
    assert wf_v2.sealed_negative_matches(tmp_path, "EXP-00032", "rsi") == [
        "other.txt (mentions strategy rsi)"]
    assert wf_v2.sealed_negative_matches(tmp_path, "EXP-00032", "dual-ma") == []


def test_evidence_record_must_stay_inside_the_repository(tmp_path):
    verdict, problem = wf_v2.evidence_verdict(tmp_path, "../outside.json")
    assert verdict is None and "outside the repository" in problem


# ---- spec and window ------------------------------------------------------------


def test_parse_spec_rejects_malformed_specs():
    assert "not a WF-v2 candidate" in wf_v2.parse_spec(None)[1][0]
    raw = _spec()
    del raw["window"]
    assert wf_v2.parse_spec(raw)[1] == ["wf_v2 spec missing keys: window"]
    assert wf_v2.parse_spec(_spec(extra=1))[1] == ["wf_v2 spec has unknown keys: extra"]
    reasons = wf_v2.parse_spec(_spec(window=["2024-08", "2022-08"], timeframe_minutes=7,
                                     position_mode="short_only"))[1]
    assert reasons == ["window start is after window end",
                       "timeframe_minutes must be a positive divisor of 1440",
                       "position_mode must be 'long_short' or 'long_flat'"]


def test_window_rules_of_section_one():
    assert wf_v2.window_reasons(_parsed()) == []
    short = wf_v2.window_reasons(_parsed(window=["2023-01", "2024-06"]))
    assert any("18 months" in r for r in short)
    no_pivot = wf_v2.window_reasons(_parsed(window=["2016-01", "2017-12"]))
    assert any("no central-bank pivot" in r for r in no_pivot)
    burned = wf_v2.window_reasons(_parsed(instruments=["EURUSD", "USDJPY"],
                                          window=["2024-01", "2026-01"]))
    assert any("exhausted" in r and "EURUSD" in r and "USDJPY" not in r for r in burned)
    assert not any("exhausted" in r for r in
                   wf_v2.window_reasons(_parsed(window=["2024-01", "2026-01"])))


# ---- data -----------------------------------------------------------------------


def _row(ts: datetime, price: float) -> dict:
    return {"timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "o_bid": price, "h_bid": price + 0.01, "l_bid": price - 0.01, "c_bid": price, "n": 1}


def test_resample_builds_bid_bars_and_measures_coverage():
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)  # Tuesday
    rows = [_row(start + timedelta(minutes=i), 100.0 + i) for i in range(480)]
    bars, coverage = wf_v2.resample_window(rows, ["2024-01"], 240)
    assert [b["timestamp"] for b in bars] == ["2024-01-02T00:00:00Z", "2024-01-02T04:00:00Z"]
    assert bars[0]["open"] == 100.0 and bars[0]["close"] == 339.0
    assert bars[0]["high"] == 339.01 and bars[0]["low"] == 99.99
    assert bars[1]["volume"] == 240
    assert coverage["present_minutes"] == 480
    assert coverage["expected_minutes"] == wf_v2.expected_minutes(["2024-01"])
    reasons = wf_v2.coverage_reasons("USDJPY", coverage)
    assert any("missing-tick rate" in r for r in reasons)

    _, gap = wf_v2.resample_window(rows, ["2023-12", "2024-01"], 240)
    assert any("no data in 2023-12" in r for r in wf_v2.coverage_reasons("USDJPY", gap))

    with pytest.raises(ValueError, match="not time-ordered"):
        wf_v2.resample_window(list(reversed(rows)), ["2024-01"], 240)


def test_weekend_minutes_are_not_expected():
    # Feb 2024: 21 weekdays incl. 4 Fridays (22h each), 4 Saturdays, 4 Sundays (2h each).
    assert wf_v2.expected_minutes(["2024-02"]) == 17 * 1440 + 4 * 1320 + 4 * 120
    assert not wf_v2._is_trading_minute(datetime(2024, 1, 5, 22, 0, tzinfo=timezone.utc))
    assert wf_v2._is_trading_minute(datetime(2024, 1, 7, 22, 0, tzinfo=timezone.utc))


# ---- positions ------------------------------------------------------------------


def _scripted(signals, reported=None):
    """Factory for a signal fn that replays `signals`; optionally reports `reported`."""
    def factory(_params):
        it = iter(signals)
        state = iter(reported) if reported is not None else None
        held = [0]

        def signal_fn(_bar):
            if state is not None:
                held[0] = next(state)
            return next(it)
        if state is not None:
            signal_fn.position = lambda: held[0]
        return signal_fn
    return factory


_EXITS = ["BUY", "SELL", "SELL", "BUY", None]  # enter long, exit, enter short, exit, idle
_HELD = [1, 0, -1, 0, 0]


@pytest.mark.parametrize("reported, mode, expected", [
    (None, "long_short", [1, -1, -1, 1, 1]),   # signal-only: stop-and-reverse
    (None, "long_flat", [1, 0, 0, 1, 1]),
    (_HELD, "long_short", [1, 0, -1, 0, 0]),   # reported: exits stay exits
    (_HELD, "long_flat", [1, 0, 0, 0, 0]),
])
def test_positions_read_reported_state_when_available(monkeypatch, reported, mode, expected):
    monkeypatch.setattr(wf_v2, "_strategy_factory", lambda _id: _scripted(_EXITS, reported))
    bars = [{"close": 1.0}] * len(_EXITS)
    assert wf_v2.positions(bars, _parsed(position_mode=mode), "EURUSD") == expected


def test_positions_reject_a_reported_size_outside_unit(monkeypatch):
    monkeypatch.setattr(wf_v2, "_strategy_factory", lambda _id: _scripted(["BUY"], [2]))
    with pytest.raises(ValueError, match="reported position 2"):
        wf_v2.positions([{"close": 1.0}], _parsed(), "EURUSD")


def test_traderdev_ema9vwap_positions_match_its_own_state():
    from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP

    rng = random.Random(3)
    price, bars = 1.10, []
    for i in range(800):
        move = rng.gauss(0, 2e-3)
        close = price * (1 + move)
        bars.append({"timestamp": f"t{i}", "open": price, "close": close,
                     "high": max(price, close) * (1 + abs(rng.gauss(0, 5e-4))),
                     "low": min(price, close) * (1 - abs(rng.gauss(0, 5e-4))), "volume": 240})
        price = close
    params = {"ema_period": 9, "vwap_period": 120, "atr_period": 14, "trail_mult": 2.0}
    spec = _parsed(strategy_id="traderdev-ema9-vwap", strategy_params=params)

    strat = TraderDevEMA9VWAP(**params)
    own = []
    for bar in bars:
        strat(dict(bar, instrument_id="EURUSD"))
        own.append(strat.position)

    assert wf_v2.positions(bars, spec, "EURUSD") == own
    stop_exits = sum(1 for a, b in zip(own, own[1:]) if a != 0 and b == 0)
    assert stop_exits > 0, "fixture never exercised a trailing-stop exit"


# ---- cost engine and statistics -------------------------------------------------


def test_short_in_a_rising_market_loses():
    closes = [100.0, 101.0, 102.0, 103.0]
    rets, traded = wf_v2.fold_returns(closes, [-1, -1, -1, -1], 0, 4)
    assert rets[0] == pytest.approx(-wf_v2.COST_RT / 2 * wf_v2.LEVERAGE)  # entry earns nothing
    assert all(r < 0 for r in rets[1:])
    assert traded == pytest.approx(wf_v2.LEVERAGE)


def test_a_flip_pays_cost_on_the_full_change_and_earns_nothing():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    rets, traded = wf_v2.fold_returns(closes, [1, 1, -1, -1, -1], 0, 5)
    assert rets[0] == pytest.approx(-wf_v2.COST_RT / 2 * wf_v2.LEVERAGE)
    assert rets[1] == pytest.approx((102 / 101 - 1) * wf_v2.LEVERAGE)
    assert rets[2] == pytest.approx(-wf_v2.COST_RT * wf_v2.LEVERAGE)  # flip = full round trip
    assert rets[3] < 0
    assert traded == pytest.approx(3 * wf_v2.LEVERAGE)


def test_spearman_handles_ties_and_constants():
    assert wf_v2.spearman([1, 1, 2, 2], [1, 2, 3, 4]) == pytest.approx(0.894427191)
    assert wf_v2.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert wf_v2.spearman([1, 2], [1, 2]) is None


def test_constant_position_fails_every_window_on_undefined_ic():
    months = wf_v2.months_between("2023-01", "2023-08")
    bars = [{"timestamp": f"{m}-{d:02d}T00:00:00Z", "close": 100.0 * 1.001 ** (i * 20 + d)}
            for i, m in enumerate(months) for d in range(1, 21)]
    result = wf_v2.evaluate(bars, [1] * len(bars), months, 1440)
    assert len(result["windows"]) == 2
    assert all(w["ic"] is None and not w["passed"] for w in result["windows"])
    assert result["criteria"]["net_oos_return"]["passed"]
    assert not result["passed"]


# ---- end to end -----------------------------------------------------------------

_HYPOTHESES = '''
from titan.research.experiment import Experiment

hypotheses = [Experiment(
    id="EXP-90001",
    question="Does an EMA 5/20 cross carry USDJPY trend across the 2022-24 policy cycle?",
    economic_rationale="Policy divergence produces persistent carry-driven flows.",
    dataset_id="dukascopy_1m_ba_prior",
    features=("close",),
    target="next_bar_return",
    params={"wf_v2": %r},
)]
'''


def _minute_stream():
    rng = random.Random(7)
    t = datetime(2022, 8, 1, tzinfo=timezone.utc)
    stop = datetime(2024, 9, 1, tzinfo=timezone.utc)
    one = timedelta(minutes=1)
    price = 135.0
    while t < stop:
        if wf_v2._is_trading_minute(t):
            price *= 1 + rng.gauss(0, 3e-4)
            yield {"timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o_bid": price,
                   "h_bid": price, "l_bid": price, "c_bid": price, "n": 1}
        t += one


@pytest.fixture
def research_root(tmp_path, monkeypatch):
    (tmp_path / "research" / "neg_results").mkdir(parents=True)
    (tmp_path / "research" / "evidence").mkdir()
    (tmp_path / "research" / "evidence" / "EXP-90001.json").write_text(
        json.dumps({"verdict": "candidate"}), encoding="utf-8")
    data = tmp_path / "research" / "dukascopy_1m_ba_prior"
    data.mkdir()
    (data / "USDJPY.json").write_text("[]", encoding="utf-8")
    shutil.copy(ROOT / wf_v2.PROTOCOL, tmp_path / wf_v2.PROTOCOL)
    (tmp_path / "research" / "hypotheses.py").write_text(_HYPOTHESES % _spec(), encoding="utf-8")
    monkeypatch.setattr(wf_v2, "load_minutes", lambda path: _minute_stream())
    return tmp_path


def test_check_only_reports_eligibility_without_writing(research_root):
    outcome = wf_v2.run("EXP-90001", root=research_root, check_only=True)
    assert outcome.status == "ELIGIBLE" and outcome.exit_code == 0, outcome.report
    assert not (research_root / wf_v2.RESULTS_DIR).exists()


def test_run_writes_a_reproducible_bundle_and_memo(research_root):
    outcome = wf_v2.run("EXP-90001", root=research_root)
    assert outcome.status in ("PASS", "FAIL"), outcome.report
    assert outcome.exit_code == (0 if outcome.status == "PASS" else 1)

    bundle = json.loads(outcome.bundle_path.read_text(encoding="utf-8"))
    result = bundle["instruments"]["USDJPY"]
    assert len(result["windows"]) == 19  # 25 months, first 6 are train-only
    assert result["windows"][0]["test_month"] == "2023-02"
    assert set(result["criteria"]) == {"window_pass_rate", "mean_sharpe", "mean_ic",
                                       "annual_turnover", "net_oos_return"}
    assert bundle["verdict"] == outcome.status
    assert bundle["protocol_sha256"]
    assert bundle["interpretation"] == wf_v2.INTERPRETATION
    assert bundle["data"]["USDJPY"]["coverage"]["missing_rate"] < wf_v2.MAX_MISSING_RATE
    assert "error" not in bundle["execution_check"]["USDJPY"]
    assert bundle["execution_check"]["USDJPY"]["rejected_intents"] == 0

    memo = outcome.memo_path.read_text(encoding="utf-8")
    assert memo.startswith(f"# WF-v2 verdict — EXP-90001: {outcome.status}")
    assert "## Decision (protocol section 7)" in memo

    first_bundle, first_memo = outcome.bundle_path.read_bytes(), outcome.memo_path.read_bytes()
    again = wf_v2.run("EXP-90001", root=research_root)
    assert again.status == outcome.status
    assert outcome.bundle_path.read_bytes() == first_bundle
    assert outcome.memo_path.read_bytes() == first_memo


def test_run_refuses_a_non_candidate_evidence_record(research_root):
    (research_root / "research" / "evidence" / "EXP-90001.json").write_text(
        json.dumps({"verdict": "rejected"}), encoding="utf-8")
    outcome = wf_v2.run("EXP-90001", root=research_root)
    assert outcome.exit_code == 2
    assert "evidence_record verdict is 'rejected'" in outcome.report
