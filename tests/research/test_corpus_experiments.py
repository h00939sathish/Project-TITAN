import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

EXPERIMENT_SCRIPTS = [
    ("EXP-00012", ROOT_DIR / "scripts" / "experiments" / "exp_00012_volume_catalyzed_compression.py", ROOT_DIR / "research" / "experiments" / "EXP-0012_evidence_bundle.json"),
    ("EXP-00013", ROOT_DIR / "scripts" / "experiments" / "exp_00013_execution_microstructure_alpha.py", ROOT_DIR / "research" / "experiments" / "EXP-0013_evidence_bundle.json"),
    ("EXP-00014", ROOT_DIR / "scripts" / "experiments" / "exp_00014_sector_lead_lag.py", ROOT_DIR / "research" / "experiments" / "EXP-0014_evidence_bundle.json"),
    ("EXP-00015", ROOT_DIR / "scripts" / "experiments" / "exp_00015_regime_momentum_breakdown.py", ROOT_DIR / "research" / "experiments" / "EXP-0015_evidence_bundle.json"),
]

@pytest.mark.parametrize("exp_id,script_path,bundle_path", EXPERIMENT_SCRIPTS)
def test_corpus_experiment_execution(exp_id, script_path, bundle_path):
    assert script_path.exists(), f"Experiment script missing: {script_path}"

    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, cwd=str(ROOT_DIR))
    assert res.returncode == 0, f"Script {exp_id} failed with error:\n{res.stderr}"

    assert bundle_path.exists(), f"Evidence bundle missing: {bundle_path}"

    with open(bundle_path, "r") as f:
        data = json.load(f)

    assert data.get("experiment_id") == exp_id
    assert "canonical_rq" in data
    assert "decision" in data
    assert "results" in data
