"""FFI enum-safety guard (audit S-03 / Path B).

Prohibits Python↔Rust enum boundary abuse: comparing Rust enum-typed values by
their ORDINAL integer (int(severity) >= 2) silently mis-evaluates if Rust
enum variants are added or re-ordered. All boundary comparisons must use NAMED
enum membership (e.g. severity == ReconciliationDriftSeverity.Critical).

This test scans the source (not the wheel) and FAILS if any risky pattern
appears, so the discipline is enforced going forward rather than a one-time
audit.

Known-legitimate exceptions (raw protocol, not Rust enums) are allowlisted.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
ALLOWED = {
    "scripts/ibkr_check_connection.py",  # IBKR TWS raw protocol tick code, not a TITAN enum
}

# Either: int(<something containing enum-ish>)  OR  <Enum>.value >= N  OR  <Enum> == N
INT_CAST = re.compile(
    r"\bint\([a-zA-Z_.]*"
    r"(state|severity|verdict|decision|phase|gate|type|side|timeframe|mode)",
    re.IGNORECASE,
)
ORDINAL = re.compile(
    r"\b(severity|verdict|decision|state|kill_switch|trading_state)"
    r"\.value\s*(>=|<=)\s*[0-9]",
    re.IGNORECASE,
)
ENUM_EQ_NUM = re.compile(
    r"\b(KillSwitchState|TradingState|ReconciliationDriftSeverity|RiskGateDecision)\s*[=!]=\s*[0-9]",
)


def _source_files(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        yield p


def test_no_ordinal_enum_casts_in_source():
    violations = []
    for p in _source_files(SRC):
        rel = str(p.relative_to(SRC))
        if rel in ALLOWED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if INT_CAST.search(line) or ORDINAL.search(line) or ENUM_EQ_NUM.search(line):
                violations.append(f"{rel}:{i}: {line.strip()}")
    assert not violations, (
        "FFI enum ordinal-comparison found — must use NAMED enum membership:\n"
        + "\n".join(violations[:20])
    )