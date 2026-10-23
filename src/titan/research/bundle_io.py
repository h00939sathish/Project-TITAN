"""Evidence-bundle persistence that does not churn on reruns."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_VOLATILE = ("generated_at",)


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _evidence(bundle: dict) -> dict:
    return {k: v for k, v in bundle.items() if k not in _VOLATILE}


def write_bundle(path: Path, bundle: dict) -> bool:
    """Persist `bundle` unless `path` already holds the same evidence.

    On an equivalent rerun the file is left byte-for-byte untouched and `bundle`
    adopts the stored generated_at, so the timestamp keeps meaning "first produced".
    Returns True when the file was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and _same(_evidence(existing), _evidence(bundle)):
            for key in _VOLATILE:
                if key in existing:
                    bundle[key] = existing[key]
            return False
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return True
