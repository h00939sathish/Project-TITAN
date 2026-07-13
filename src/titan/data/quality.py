"""Quality checks and quarantine for market data."""

from dataclasses import dataclass, field


@dataclass
class QuarantineReport:
    total_records: int = 0
    passed: int = 0
    quarantined: list[dict] = field(default_factory=list)

    @property
    def quarantine_count(self) -> int:
        return len(self.quarantined)


def validate_and_quarantine(records: list[dict], normalize_fn) -> tuple:
    """Run records through normalize_fn. Good records pass; bad records are quarantined."""
    report = QuarantineReport(total_records=len(records))
    good = []
    seen = set()
    for row in records:
        result = normalize_fn(row)
        if isinstance(result, str):
            report.quarantined.append({"row": row, "reason": result})
        else:
            key = (result["instrument_id"], result["timestamp"])
            if key in seen:
                report.quarantined.append({"row": row, "reason": f"Duplicate: {key}"})
            else:
                seen.add(key)
                good.append(result)
                report.passed += 1
    return report, good
