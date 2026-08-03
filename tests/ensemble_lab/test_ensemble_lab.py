"""Tests for ensemble lab harness."""

import argparse
import json
from pathlib import Path

from scripts.ensemble_lab import main


def _mock_args(**overrides):
    data = {
        "mode": "monitor",
        "manifest_dir": "logs/ensemble_lab",
        "report_dir": "logs/ensemble_lab",
        "run_id": "test",
        "bars": 200,
        "instrument": "SYNTH-1",
        "manifest_path": "logs/ensemble_lab/monitor_test.jsonl",
        "buy_threshold": 0.6,
        "sell_threshold": -0.6,
        "min_trades": 20,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_monitor_writes_records(tmp_path):
    manifest_path = Path(tmp_path) / "monitor_test.jsonl"
    args = _mock_args(manifest_dir=str(tmp_path), manifest_path=str(manifest_path))
    # Directly run the monitor logic
    from scripts.ensemble_lab import _run_monitor
    manifest_path = _run_monitor(args)
    assert manifest_path.exists()
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 0
    first = json.loads(lines[0])
    assert first["instrument"] == "SYNTH-1"
    assert first["signal"] in {"BUY", "SELL", "HOLD"}


def test_audit_sets_threshold(tmp_path):
    from scripts.ensemble_lab import _run_monitor, _run_audit
    manifest_path = _run_monitor(_mock_args(manifest_dir=str(tmp_path), manifest_path=str(Path(tmp_path) / "m.jsonl")))
    report_path = _run_audit(_mock_args(manifest_path=str(manifest_path), report_dir=str(tmp_path)))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["threshold"] == 0.7
    assert "correlations" in report


def test_optimize_returns_sorted_candidates(tmp_path):
    from scripts.ensemble_lab import _run_monitor, _run_optimize
    manifest_path = _run_monitor(_mock_args(manifest_dir=str(tmp_path), manifest_path=str(Path(tmp_path) / "m.jsonl")))
    report_path = _run_optimize(_mock_args(manifest_path=str(manifest_path), report_dir=str(tmp_path)))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    accepted = [c["accepted_count"] for c in report["candidates"]]
    assert accepted == sorted(accepted, reverse=True)


def test_watch_can_transition(tmp_path):
    from scripts.ensemble_lab import _run_watch
    report_path = _run_watch(_mock_args(manifest_dir=str(tmp_path), manifest_path=str(Path(tmp_path) / "m.jsonl")))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "final_statuses" in report
    assert "transitions" in report
