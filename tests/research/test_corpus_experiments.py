import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

EXPERIMENT_SCRIPTS = [
    ("EXP-00012", ROOT_DIR / "scripts" / "experiments" / "exp_00012_volume_catalyzed_compression.py", ROOT_DIR / "research" / "experiments" / "EXP-0012_evidence_bundle.json"),
    ("EXP-00013", ROOT_DIR / "scripts" / "experiments" / "exp_00013_execution_microstructure_alpha.py", ROOT_DIR / "research" / "experiments" / "EXP-0013_evidence_bundle.json"),
    ("EXP-00014", ROOT_DIR / "scripts" / "experiments" / "exp_00014_sector_lead_lag.py", ROOT_DIR / "research" / "experiments" / "EXP-0014_evidence_bundle.json"),
    ("EXP-00015", ROOT_DIR / "scripts" / "experiments" / "exp_00015_regime_momentum_breakdown.py", ROOT_DIR / "research" / "experiments" / "EXP-0015_evidence_bundle.json"),
]

# Each script writes its evidence bundle to a hardcoded EVIDENCE_PATH under
# research/experiments/. Re-running the script in the test would REWRITE the
# production evidence record (fresh timestamp, possible result drift) — the
# test harness mutating the evidence it verifies is an integrity violation
# (observed: 4 bundles' timestamps rewritten by a plain suite run). We execute
# a temp copy of the script with EVIDENCE_PATH redirected to a temp dir, so the
# script still runs end-to-end but production evidence stays untouched.

def _redirected_script_copy(script_path: Path, tmp_out_dir: Path) -> Path:
    """Copy the script to a temp location with EVIDENCE_PATH redirected."""
    src = script_path.read_text(encoding="utf-8")
    # Redirect any EVIDENCE_PATH assignment to the temp dir, preserving the
    # original filename so the bundle-write logic is otherwise untouched.
    def _sub(m: re.Match) -> str:
        indent = m.group(1)
        name = m.group(2)
        return f'{indent}{name} = Path(r"{tmp_out_dir.as_posix()}") / "{script_path.stem}_evidence_bundle.json"'
    new_src = re.sub(
        r'^(\s*)(EVIDENCE_PATH|BUNDLE_PATH|OUTPUT_PATH)\s*=\s*.*$',
        _sub,
        src,
        flags=re.MULTILINE,
    )
    if new_src == src:
        raise AssertionError(
            f"No EVIDENCE_PATH/BUNDLE_PATH assignment found in {script_path.name} — "
            "cannot redirect its output; refusing to run it against production evidence."
        )
    tmp_script = Path(tmp_out_dir) / script_path.name
    tmp_script.write_text(new_src, encoding="utf-8")
    return tmp_script

@pytest.mark.parametrize("exp_id,script_path,bundle_path", EXPERIMENT_SCRIPTS)
def test_corpus_experiment_execution(exp_id, script_path, bundle_path):
    assert script_path.exists(), f"Experiment script missing: {script_path}"
    assert bundle_path.exists(), f"Production evidence bundle missing: {bundle_path}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        redirected = _redirected_script_copy(script_path, tmp_dir)

        res = subprocess.run(
            [sys.executable, str(redirected)],
            capture_output=True, text=True, cwd=str(ROOT_DIR),
        )
        assert res.returncode == 0, f"Script {exp_id} failed with error:\n{res.stderr}"

        out_bundle = tmp_dir / f"{script_path.stem}_evidence_bundle.json"
        assert out_bundle.exists(), f"Redirected evidence bundle missing: {out_bundle}"

        with open(out_bundle, "r") as f:
            data = json.load(f)

    assert data.get("experiment_id") == exp_id
    assert "canonical_rq" in data
    assert "decision" in data
    assert "results" in data

    # Production evidence must be byte-identical after the test (no mutation).
    before = bundle_path.read_bytes()
    after = bundle_path.read_bytes()
    assert before == after, (
        f"Production evidence bundle {bundle_path.name} was mutated by the test run. "
        "Test harness must never write to production evidence."
    )
