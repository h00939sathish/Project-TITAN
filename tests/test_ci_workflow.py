"""Regression lock for the CI workflow trigger (ADR-034).

The repository trunk is `master`. The CI workflow previously triggered only on
`main`, a branch that does not exist, so the entire gate never ran. These tests
parse the checked-in workflow without a third-party YAML dependency (the CI job
installs none) and assert the trigger matches the real trunk and the advisory
typing posture is intact.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"

TRUNK = "master"
PHANTOM = "main"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _branch_lists() -> list[list[str]]:
    """Return each inline ``branches: [...]`` list as parsed tokens."""
    matches = re.findall(r"branches:\s*\[([^\]]*)\]", _text())
    assert matches, "no inline `branches: [...]` lists found in ci.yml"
    return [[tok.strip() for tok in block.split(",") if tok.strip()] for block in matches]


def test_workflow_file_exists() -> None:
    assert WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}"


def test_every_branch_trigger_targets_trunk_not_phantom() -> None:
    lists = _branch_lists()
    # Both `push` and `pull_request` must be present.
    assert len(lists) >= 2, f"expected >=2 branch triggers, found {len(lists)}"
    for branches in lists:
        assert TRUNK in branches, f"trigger does not target trunk {TRUNK!r}: {branches}"
        assert PHANTOM not in branches, f"trigger references non-existent {PHANTOM!r}: {branches}"


def test_mypy_step_is_advisory_and_typed_run_present() -> None:
    text = _text()
    assert re.search(r"run:\s*mypy\s+src/titan", text), "mypy run step missing"
    # The step that runs mypy must carry continue-on-error (advisory posture).
    # Find the continue-on-error flag within the mypy step block.
    mypy_block = re.search(
        r"run:\s*mypy\s+src/titan[^\n]*\n(\s+continue-on-error:\s*true)",
        text,
    )
    assert mypy_block, "mypy step is not marked `continue-on-error: true` (ADR-034)"
