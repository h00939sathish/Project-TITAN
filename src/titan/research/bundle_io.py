"""Evidence-bundle persistence and deterministic digests that do not churn on reruns."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_SIG_DIGITS = 10
DEFAULT_DIGEST_SCHEME = "v1"
_VOLATILE = ("generated_at", "digest")


def canonicalize_floats(obj: Any, sig_digits: int = DEFAULT_SIG_DIGITS) -> Any:
    """Recursively canonicalize floating-point numbers to fixed significant digits.

    Eliminates ~1e-16 floating-point summation / machine precision noise across reruns.
    Preserves booleans, integers, strings, None, and special floats (NaN, Inf).
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return obj
        if obj == 0.0:
            return 0.0
        return float(f"{obj:.{sig_digits}g}")
    if isinstance(obj, dict):
        return {k: canonicalize_floats(v, sig_digits=sig_digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [canonicalize_floats(x, sig_digits=sig_digits) for x in obj]
    if isinstance(obj, tuple):
        return tuple(canonicalize_floats(x, sig_digits=sig_digits) for x in obj)
    return obj


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


def bundle_digest(
    bundle: dict,
    scheme: str | None = None,
    sig_digits: int = DEFAULT_SIG_DIGITS,
) -> str:
    """Compute a deterministic, versioned cryptographic digest for an evidence bundle.

    Excludes volatile fields ('generated_at', 'digest').
    Applies float canonicalization to eliminate ~1e-16 floating-point noise across reruns.
    Versions the hashing algorithm via the 'digest_scheme' field.
    """
    actual_scheme = scheme or bundle.get("digest_scheme", DEFAULT_DIGEST_SCHEME)
    if actual_scheme != "v1":
        raise ValueError(f"Unsupported digest_scheme: {actual_scheme}")

    content = {k: v for k, v in bundle.items() if k not in _VOLATILE}
    content["digest_scheme"] = actual_scheme

    canonical = canonicalize_floats(content, sig_digits=sig_digits)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_bundle(
    path: Path,
    bundle: dict,
    *,
    canonicalize: bool = True,
    sig_digits: int = DEFAULT_SIG_DIGITS,
) -> bool:
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
    data_to_write = canonicalize_floats(bundle, sig_digits=sig_digits) if canonicalize else bundle
    path.write_text(json.dumps(data_to_write, indent=2), encoding="utf-8")
    return True
