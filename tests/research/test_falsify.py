"""Tests for the deterministic falsification probes."""

from __future__ import annotations

from titan.research.falsify import FAIL, UNVERIFIABLE, WARN, falsify


def _trade(side: str, pnl: float, timestamp: str, *, price: float = 100.0, qty: int = 10) -> dict:
    return {
        "side": side,
        "pnl": pnl,
        "timestamp": timestamp,
        "price": price,
        "qty": qty,
        "commission": 1.0,
        "spread_cost": 0.5,
        "slippage_cost": 0.5,
    }


def _clean_payload() -> dict:
    return {
        "equity_curve": [100_000.0, 100_000.0, 100_998.0],
        "trades": [
            _trade("buy", 0.0, "t1"),
            _trade("sell", 998.0, "t4"),
        ],
        "reported": {"total_trades": 1, "sharpe_ratio": 2.0, "years": 4.0},
        "n_bars": 3,
        "verdict": "candidate",
        "replicated": True,
        "gates": [{"name": "walk_forward", "passed": True}],
    }


def test_clean_round_trip_passes() -> None:
    report = falsify(_clean_payload())
    assert report.verdict != FAIL
    assert not [f for f in report.findings if f.status == FAIL]


def test_double_counted_pnl_is_rejected() -> None:
    payload = _clean_payload()
    payload["trades"][0]["pnl"] = 998.0  # same round-trip pnl copied onto the entry leg
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "pnl_identity")
    assert finding.status == FAIL
    assert "double-counts" in finding.detail


def test_missing_exit_is_rejected() -> None:
    payload = _clean_payload()
    payload["trades"] = [payload["trades"][0]]
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "pnl_identity")
    assert finding.status == FAIL
    assert "no exit leg" in finding.detail


def test_zero_costs_are_rejected() -> None:
    payload = _clean_payload()
    for trade in payload["trades"]:
        trade["commission"] = 0.0
        trade["spread_cost"] = 0.0
        trade["slippage_cost"] = 0.0
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "costs")
    assert finding.status == FAIL


def test_leg_counted_as_trade_is_rejected() -> None:
    payload = _clean_payload()
    payload["reported"]["total_trades"] = 2
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "trade_count")
    assert finding.status == FAIL


def test_same_bar_fill_is_rejected() -> None:
    payload = _clean_payload()
    payload["trades"][0]["signal_timestamp"] = "t1"
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "lookahead")
    assert finding.status == FAIL


def test_failed_gate_cannot_promote() -> None:
    payload = _clean_payload()
    payload["gates"] = [{"name": "walk_forward", "passed": False}]
    payload["verdict"] = "promote"
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "gate_integrity")
    assert finding.status == FAIL


def test_unreplicated_result_cannot_promote() -> None:
    payload = _clean_payload()
    payload["verdict"] = "promote"
    payload["replicated"] = False
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "gate_integrity")
    assert finding.status == FAIL


def test_underpowered_result_is_a_warning_not_a_rejection() -> None:
    payload = _clean_payload()
    payload["reported"] = {"total_trades": 1, "sharpe_ratio": 1.0, "years": 0.25}
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "power")
    assert finding.status == WARN


def test_missing_signal_timestamp_is_unverifiable() -> None:
    payload = _clean_payload()
    report = falsify(payload)
    finding = next(f for f in report.findings if f.probe == "lookahead")
    assert finding.status == UNVERIFIABLE
