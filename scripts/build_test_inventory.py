import csv, subprocess, sys, os
from collections import Counter

ROOT = "D:/projects/Project TITAN"
r = subprocess.run(
    [sys.executable, "-m", "pytest", "--collect-only", "-q"],
    cwd=ROOT, capture_output=True, text=True, timeout=300,
)
if r.returncode != 0:
    print("WARN collect rc:", r.returncode, r.stderr[-300:])
lines = [l.strip() for l in r.stdout.splitlines() if "::" in l.strip()]
tests = []
for l in lines:
    if not (l.startswith("tests/") or l.startswith("tests\\")):
        continue
    parts = l.split("::")
    if len(parts) >= 2:
        tests.append((parts[0], "::".join(parts[1:])))

rows = []
for fpath, node in tests:
    node_parts = node.split("::")
    test_name = node_parts[-1]
    cls = node_parts[-2] if len(node_parts) > 1 else ""
    rows.append({"file": fpath, "class": cls, "test": test_name,
                 "status": "pending", "note": ""})

out = os.path.join(ROOT, "research", "test_inventory.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["file", "class", "test", "status", "note"])
    w.writeheader()
    w.writerows(rows)
print(f"Wrote {len(rows)} tests to {out}")
dirs = Counter(r["file"].split("/")[1] for r in rows)
for d, c in dirs.most_common():
    print(f"  {d}: {c}")
