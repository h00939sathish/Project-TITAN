"""`titan research queue`: validation, the protocol pin, logging, and the write boundary."""
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from test_wf_v2 import _HYPOTHESES, ROOT, _minute_stream, _spec
from titan.cli import cli
from titan.research import queue, wf_v2


def _write_queue(root: Path, body: str) -> None:
    (root / queue.QUEUE_FILE).write_text(body, encoding="utf-8")


def _log(root: Path) -> list[dict]:
    path = root / queue.RUN_LOG
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


@pytest.fixture
def repo(tmp_path, monkeypatch):
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
    _write_queue(tmp_path, "")
    return tmp_path


def _fake_run(calls: list, fail: set[str] = frozenset()):
    def run(exp_id, root, check_only=False):
        calls.append(exp_id)
        if exp_id in fail:
            raise RuntimeError(f"boom in {exp_id}")
        return wf_v2.Outcome(exp_id, "REFUSED", ["fake"], None, None, f"{exp_id}: REFUSED")
    return run


# ---- the real repository ---------------------------------------------------------


def test_real_queue_parses_and_protocol_matches_the_pin():
    ids, max_runs = queue.load_queue(ROOT)
    assert all(queue._ID.match(i) for i in ids)
    assert 1 <= max_runs <= queue.MAX_RUNS_CAP
    assert queue.protocol_digest(ROOT / wf_v2.PROTOCOL) == queue.PINNED_PROTOCOL_SHA256


def test_protocol_digest_ignores_line_endings(tmp_path):
    (tmp_path / "lf").write_bytes(b"a\nb\n")
    (tmp_path / "crlf").write_bytes(b"a\r\nb\r\n")
    assert queue.protocol_digest(tmp_path / "lf") == queue.protocol_digest(tmp_path / "crlf")
    assert queue.protocol_digest(tmp_path / "missing") is None


# ---- queue file validation -------------------------------------------------------


@pytest.mark.parametrize("body, needle", [
    ('[[experiment]]\nid = "EXP-42"\n', "id must look like EXP-00042"),
    ('[[experiment]]\nid = "EXP-00042"\n[[experiment]]\nid = "EXP-00042"\n', "queued twice"),
    ('promote = true\n', "unknown keys ['promote']"),
    ('[[experiment]]\nid = "EXP-00042"\nlive = true\n', "unknown keys ['live']"),
    ('max_runs_per_night = 0\n', "max_runs_per_night"),
    ('max_runs_per_night = 21\n', "max_runs_per_night"),
    ('max_runs_per_night = true\n', "max_runs_per_night"),
    ('experiment = "EXP-00042"\n', "must be a table"),
    ('[[experiment\n', "research/queue.toml:"),
])
def test_load_queue_rejects_malformed_files(repo, body, needle):
    _write_queue(repo, body)
    with pytest.raises(queue.QueueError, match=None) as exc:
        queue.load_queue(repo)
    assert needle in str(exc.value)


def test_missing_queue_file_aborts_and_is_logged(repo, monkeypatch):
    (repo / queue.QUEUE_FILE).unlink()
    calls: list = []
    monkeypatch.setattr(wf_v2, "run", _fake_run(calls))
    report = queue.run_queue(repo)
    assert (report.status, report.exit_code, calls) == ("ABORTED", 3, [])
    [record] = _log(repo)
    assert record["exp_id"] == "*" and "not found" in record["error"]


# ---- runner ------------------------------------------------------------------------


def test_empty_queue_runs_nothing(repo, monkeypatch):
    calls: list = []
    monkeypatch.setattr(wf_v2, "run", _fake_run(calls))
    report = queue.run_queue(repo)
    assert (report.status, report.exit_code, calls) == ("OK", 0, [])
    assert report.lines == ["queue: 0 queued, running 0"]


def test_changed_protocol_aborts_before_any_hypothesis(repo, monkeypatch):
    _write_queue(repo, '[[experiment]]\nid = "EXP-90001"\n')
    protocol = repo / wf_v2.PROTOCOL
    protocol.write_bytes(protocol.read_bytes() + b"\nrelaxed: Sharpe > 0.1\n")
    calls: list = []
    monkeypatch.setattr(wf_v2, "run", _fake_run(calls))
    report = queue.run_queue(repo)
    assert (report.status, report.exit_code, calls) == ("ABORTED", 3, [])
    [record] = _log(repo)
    assert record["exp_id"] == "*" and record["status"] == "ERROR"
    assert record["protocol_sha256"] == queue.protocol_digest(protocol)
    assert not (repo / wf_v2.RESULTS_DIR).exists()


def test_a_crash_is_logged_and_the_night_continues(repo, monkeypatch):
    _write_queue(repo, '[[experiment]]\nid = "EXP-00001"\n[[experiment]]\nid = "EXP-00002"\n')
    calls: list = []
    monkeypatch.setattr(wf_v2, "run", _fake_run(calls, fail={"EXP-00001"}))
    report = queue.run_queue(repo)
    assert (report.status, report.exit_code) == ("ERRORS", 1)
    assert calls == ["EXP-00001", "EXP-00002"]
    first, second = _log(repo)
    assert (first["exp_id"], first["status"], first["exit_code"]) == ("EXP-00001", "ERROR", 3)
    assert "boom in EXP-00001" in first["error"]
    assert (second["exp_id"], second["status"], second["reasons"]) == ("EXP-00002", "REFUSED",
                                                                       ["fake"])
    assert first["trigger"] == "queue" and first["protocol_sha256"] == queue.PINNED_PROTOCOL_SHA256


def test_entries_over_the_nightly_cap_are_deferred(repo, monkeypatch):
    ids = [f"EXP-0000{i}" for i in range(1, 5)]
    _write_queue(repo, "max_runs_per_night = 2\n"
                 + "".join(f'[[experiment]]\nid = "{i}"\n' for i in ids))
    calls: list = []
    monkeypatch.setattr(wf_v2, "run", _fake_run(calls))
    report = queue.run_queue(repo)
    assert calls == ids[:2]
    assert [r["exp_id"] for r in _log(repo)] == ids[:2]
    assert report.lines[0] == "queue: 4 queued, running 2"
    assert report.lines[-2:] == [f"{i}: deferred (over max_runs_per_night=2)" for i in ids[2:]]


def test_check_only_writes_nothing_but_the_log(repo):
    _write_queue(repo, '[[experiment]]\nid = "EXP-90001"\n')
    before = _files(repo)
    report = queue.run_queue(repo, check_only=True)
    assert report.status == "OK", report.lines
    after = _files(repo)
    assert set(after) - set(before) == {queue.RUN_LOG}
    assert all(after[p] == before[p] for p in before)
    [record] = _log(repo)
    assert (record["mode"], record["status"], record["bundle"]) == ("check", "ELIGIBLE", None)


def test_a_full_run_only_writes_under_research_wf_v2(repo):
    _write_queue(repo, '[[experiment]]\nid = "EXP-90001"\nnote = "synthetic"\n')
    before = _files(repo)
    report = queue.run_queue(repo)
    assert report.status == "OK", report.lines
    after = _files(repo)
    changed = {p for p in after if after[p] != before.get(p)}
    assert changed and all(p.startswith("research/wf_v2/") for p in changed), changed
    assert set(before) <= set(after)
    [record] = _log(repo)
    assert record["status"] in ("PASS", "FAIL")
    assert record["bundle"] == f"{wf_v2.RESULTS_DIR}/EXP-90001-wf_v2-bundle.json"
    assert record["memo"] == f"{wf_v2.RESULTS_DIR}/EXP-90001-wf_v2-verdict.md"
    assert record["protocol_sha256"] == queue.PINNED_PROTOCOL_SHA256


# ---- CLI ---------------------------------------------------------------------------


@pytest.mark.parametrize("status, code", [("OK", 0), ("ERRORS", 1), ("ABORTED", 3)])
def test_cli_queue_exit_codes(status, code, monkeypatch):
    seen = {}

    def fake(check_only=False):
        seen["check_only"] = check_only
        return queue.QueueReport(status, ["line one", "line two"])

    monkeypatch.setattr(queue, "run_queue", fake)
    result = CliRunner().invoke(cli, ["research", "queue", "--check-only"])
    assert result.exit_code == code, result.output
    assert result.output == "line one\nline two\n"
    assert seen == {"check_only": True}
