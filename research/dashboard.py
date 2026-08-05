# Research Dashboard — summarizes the health and outcomes of the pipeline.

import json
from pathlib import Path
from typing import Any


def load_library(path: str | Path = "research/results/library.json") -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return list(data.values())


def dashboard(library_path: str | Path = "research/results/library.json") -> dict[str, Any]:
    """Compute pipeline health metrics from the Negative Results Library."""
    entries = load_library(library_path)

    total = len(entries)
    by_decision: dict[str, int] = {}
    by_class: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    ics: list[float] = []
    samples: list[int] = []
    ci_widths: list[float] = []

    for e in entries:
        d = e.get("decision", "unknown")
        by_decision[d] = by_decision.get(d, 0) + 1

        cls = e.get("hypothesis_class", "unclassified")
        by_class[cls] = by_class.get(cls, 0) + 1

        ft = e.get("failure_type", "")
        if ft:
            for ftype in ft.split(";"):
                ftype = ftype.strip()
                if ftype:
                    by_failure[ftype] = by_failure.get(ftype, 0) + 1

        if e.get("ic") is not None:
            ics.append(e["ic"])
        if e.get("sample_size"):
            samples.append(e["sample_size"])

    mean_ic = sum(ics) / len(ics) if ics else 0.0
    mean_sample = sum(samples) / len(samples) if samples else 0

    return {
        "experiments_run": total,
        "by_decision": by_decision,
        "by_class": by_class,
        "by_failure_type": by_failure,
        "median_ic": sorted(ics)[len(ics) // 2] if ics else 0.0,
        "mean_ic": round(mean_ic, 4),
        "mean_sample_size": mean_sample,
        "promote_rate": round(by_decision.get("promote", 0) / max(total, 1), 2),
        "reject_rate": round(by_decision.get("reject", 0) / max(total, 1), 2),
    }


def print_dashboard(d: dict[str, Any] | None = None):
    if d is None:
        d = dashboard()

    print("╔══════════════════════════════════════════════╗")
    print("║      TITAN Research Pipeline Dashboard       ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Experiments Run:  {d['experiments_run']}")
    print(f"  Median IC:        {d['median_ic']:.4f}")
    print(f"  Mean IC:          {d['mean_ic']:.4f}")
    print(f"  Mean Sample:      {d['mean_sample_size']}")
    print()
    print("  By Decision:")
    for decision, count in sorted(d["by_decision"].items()):
        icon = {"promote": "🟢", "refine": "🟡", "reject": "🔴", "archive": "⬜"}.get(decision, "❓")
        print(f"    {icon} {decision.title()}: {count}")
    print(f"    Promote rate: {d['promote_rate']:.0%}")
    print(f"    Reject rate:  {d['reject_rate']:.0%}")
    print()
    if d["by_class"]:
        print("  By Hypothesis Class:")
        for cls, count in sorted(d["by_class"].items()):
            print(f"    {cls}: {count}")
    print()
    if d["by_failure_type"]:
        print("  Failure Types:")
        for ftype, count in sorted(d["by_failure_type"].items()):
            print(f"    {ftype}: {count}")


if __name__ == "__main__":
    print_dashboard()
