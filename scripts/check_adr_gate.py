#!/usr/bin/env python3
"""Lightweight ADR Governance Checker.

Verifies that Architectural Decision Records (ADRs) in docs/adr/ and docs/
contain required governance headers (Status, Owner/Owners/Author, Date).
"""

import sys
from pathlib import Path

REQUIRED_HEADER_GROUPS = [
    ["status"],
    ["date"],
    ["owner", "owners", "author", "authority", "decision"],
]



def check_adr_file(filepath: Path) -> list[str]:
    errors = []
    content = filepath.read_text(encoding="utf-8", errors="ignore").lower()
    
    for group in REQUIRED_HEADER_GROUPS:
        found = any(
            f"{header}:" in content or f"**{header}:**" in content or f"**{header}**" in content
            for header in group
        )
        if not found:
            errors.append(f"Missing required header group '{'/'.join(group)}' in {filepath.name}")
            
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    adr_dirs = [repo_root / "docs" / "adr", repo_root / "docs"]
    adr_files = []

    for d in adr_dirs:
        if d.exists():
            adr_files.extend([f for f in d.glob("ADR-*.md")])
            adr_files.extend([f for f in d.glob("adr-*.md")])

    if not adr_files:
        print("[ADR GATE] No ADR files found to validate.")
        return 0

    all_errors = []
    for adr_path in set(adr_files):
        errs = check_adr_file(adr_path)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"[ADR GATE PASSED] {adr_path.name}")

    if all_errors:
        print("\n[ADR GATE FAILED] Governance errors detected:")
        for err in all_errors:
            print(f" - {err}")
        return 1

    print(f"\n[ADR GATE PASSED] All {len(set(adr_files))} ADR files adhere to governance header standards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
