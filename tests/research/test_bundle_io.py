import json

from titan.research.bundle_io import write_bundle


def _bundle(value=0.1, stamp="2026-01-01T00:00:00+00:00"):
    return {"hypothesis_id": "X-1", "oos": {"sharpe": value, "n": 3}, "generated_at": stamp}


def test_first_write_creates_the_file(tmp_path):
    out = tmp_path / "b.json"
    assert write_bundle(out, _bundle()) is True
    assert json.loads(out.read_text(encoding="utf-8"))["oos"]["sharpe"] == 0.1


def test_rerun_with_identical_evidence_keeps_file_and_original_timestamp(tmp_path):
    out = tmp_path / "b.json"
    write_bundle(out, _bundle(stamp="2026-01-01T00:00:00+00:00"))
    before = out.read_bytes()
    rerun = _bundle(stamp="2026-10-23T00:00:00+00:00")
    assert write_bundle(out, rerun) is False
    assert out.read_bytes() == before
    assert rerun["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_float_noise_is_not_a_change(tmp_path):
    out = tmp_path / "b.json"
    write_bundle(out, _bundle(value=0.1))
    assert write_bundle(out, _bundle(value=0.1 + 1e-16, stamp="later")) is False


def test_real_change_is_written_with_the_new_timestamp(tmp_path):
    out = tmp_path / "b.json"
    write_bundle(out, _bundle(value=0.1))
    assert write_bundle(out, _bundle(value=0.2, stamp="later")) is True
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["oos"]["sharpe"] == 0.2
    assert data["generated_at"] == "later"


def test_structural_change_is_written(tmp_path):
    out = tmp_path / "b.json"
    write_bundle(out, _bundle())
    changed = _bundle(stamp="later")
    changed["oos"]["extra"] = 1
    assert write_bundle(out, changed) is True


def test_unreadable_existing_file_is_replaced(tmp_path):
    out = tmp_path / "b.json"
    out.write_text("{not json", encoding="utf-8")
    assert write_bundle(out, _bundle()) is True
    assert json.loads(out.read_text(encoding="utf-8"))["hypothesis_id"] == "X-1"
