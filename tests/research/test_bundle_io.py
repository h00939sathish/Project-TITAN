import json
import math
import pytest

from titan.research.bundle_io import (
    DEFAULT_DIGEST_SCHEME,
    DEFAULT_SIG_DIGITS,
    bundle_digest,
    canonicalize_floats,
    write_bundle,
)


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


def test_canonicalize_floats_preserves_non_floats():
    raw = {
        "flag": True,
        "count": 42,
        "name": "momentum",
        "missing": None,
        "list": [False, 10, "abc"],
        "tuple": (True, 5),
    }
    canonical = canonicalize_floats(raw)
    assert canonical == raw
    assert isinstance(canonical["flag"], bool)
    assert isinstance(canonical["count"], int)
    assert isinstance(canonical["list"][0], bool)


def test_canonicalize_floats_eliminates_float_noise():
    a = 0.7003023838697694
    b = 0.7003023838697693
    assert a != b
    assert canonicalize_floats(a, sig_digits=10) == canonicalize_floats(b, sig_digits=10)
    assert canonicalize_floats(a, sig_digits=12) == canonicalize_floats(b, sig_digits=12)


def test_canonicalize_floats_handles_specials_and_zeros():
    assert canonicalize_floats(0.0) == 0.0
    assert canonicalize_floats(-0.0) == 0.0
    nan_val = canonicalize_floats(float("nan"))
    assert math.isnan(nan_val)
    assert canonicalize_floats(float("inf")) == float("inf")
    assert canonicalize_floats(float("-inf")) == float("-inf")


def test_bundle_digest_deterministic_across_float_noise_and_timestamps():
    b1 = {
        "hypothesis_id": "EQ-001",
        "oos": {"sharpe": 0.7003023838697694, "drawdown": 0.08303612083882615},
        "generated_at": "2026-09-20T08:15:52.717079+00:00",
    }
    b2 = {
        "hypothesis_id": "EQ-001",
        "oos": {"sharpe": 0.7003023838697693, "drawdown": 0.08303612083882616},
        "generated_at": "2026-10-23T13:13:21.669028+00:00",
    }
    d1 = bundle_digest(b1)
    d2 = bundle_digest(b2)
    assert len(d1) == 64
    assert d1 == d2


def test_bundle_digest_independent_of_key_order():
    b1 = {"a": 1, "b": 2.0, "c": [3, 4.0]}
    b2 = {"c": [3, 4.0], "b": 2.0, "a": 1}
    assert bundle_digest(b1) == bundle_digest(b2)


def test_bundle_digest_ignores_self_digest():
    b1 = {"hypothesis_id": "EQ-001", "sharpe": 0.5}
    d1 = bundle_digest(b1)
    b2 = {"hypothesis_id": "EQ-001", "sharpe": 0.5, "digest": d1}
    assert bundle_digest(b2) == d1


def test_bundle_digest_versioned_by_digest_scheme():
    b = {"hypothesis_id": "EQ-001", "sharpe": 0.5}
    d_default = bundle_digest(b)
    d_explicit_v1 = bundle_digest(b, scheme="v1")
    assert d_default == d_explicit_v1

    # An embedded digest_scheme matches the scheme
    b_with_scheme = dict(b, digest_scheme="v1")
    assert bundle_digest(b_with_scheme) == d_default

    # Unsupported future scheme raises ValueError
    with pytest.raises(ValueError, match="Unsupported digest_scheme"):
        bundle_digest(b, scheme="v2")


def test_bundle_digest_detects_real_differences():
    b1 = {"hypothesis_id": "EQ-001", "sharpe": 0.5}
    b2 = {"hypothesis_id": "EQ-001", "sharpe": 0.6}
    assert bundle_digest(b1) != bundle_digest(b2)
