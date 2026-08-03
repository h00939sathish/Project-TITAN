"""Quality checks and quarantine for market data."""

from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class QuarantineReport:
    total_records: int = 0
    passed: int = 0
    quarantined: list[dict] = field(default_factory=list)

    @property
    def quarantine_count(self) -> int:
        return len(self.quarantined)


def _is_business_day_gap(prev_date: datetime, curr_date: datetime) -> bool:
    """Return True if there is at least 1 weekday between prev_date and curr_date (exclusive).

    Fri->Mon (calendar diff=3d, 0 business days between)         -> no gap
    Fri->Tue (calendar diff=4d, 1 business day between = Monday)  -> gap
    """
    if curr_date <= prev_date:
        return True
    days_diff = (curr_date - prev_date).days
    if days_diff == 1:
        return False
    business_days = 0
    for i in range(1, days_diff):
        d = prev_date + timedelta(days=i)
        if d.weekday() < 5:  # Mon=0 … Fri=4
            business_days += 1
    return business_days > 0


def validate_and_quarantine(
    records: list[dict],
    normalize_fn,
    *,
    pass_through_unknown: bool = False,
    detect_gaps: bool = False,
    detect_intraday_gaps: bool = False,
    expected_bar_interval_minutes: int = 15,
) -> tuple:
    """Run records through normalize_fn. Good records pass; bad records are quarantined.

    Parameters
    ----------
    pass_through_unknown : bool
        When True, rows whose normalizer returns an "Unknown symbol" error are
        given a fallback normalized record instead of quarantined.  This keeps
        the pipeline survivorship-safe.
    detect_gaps : bool
        When True, consecutive bars for the same instrument_id are checked for
        calendar gaps of one or more business days (weekend-aware).  Rows that
        create a gap are quarantined.
    detect_intraday_gaps : bool
        When True, consecutive intraday bars on the same day exceeding 5x expected
        interval are quarantined.
    """
    report = QuarantineReport(total_records=len(records))
    good = []
    seen = set()
    last_timestamp: dict[str, datetime] = {}
    for row in records:
        result = normalize_fn(row)

        # -- pass-through for unknown / delisted symbols --------------------
        if isinstance(result, str) and pass_through_unknown and result.startswith("Unknown symbol:"):
            try:
                symbol = row.get("symbol", "").strip().upper() or "UNKNOWN"
                date_str = row.get("date", "").strip()
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if "T" in date_str else datetime.strptime(date_str, "%Y-%m-%d")
                result = {
                    "instrument_id": symbol,
                    "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": int(float(row.get("volume", 0))),
                }
            except (ValueError, TypeError):
                pass  # fallback failed → keep original error string

        if isinstance(result, str):
            report.quarantined.append({"row": row, "reason": result})
        else:
            key = (result["instrument_id"], result["timestamp"])
            if key in seen:
                report.quarantined.append({"row": row, "reason": f"Duplicate: {key}"})
            else:
                seen.add(key)

                # -- gap detection ------------------------------------------
                inst = result["instrument_id"]
                ts_str = result["timestamp"].replace("Z", "+00:00")
                curr_dt = datetime.fromisoformat(ts_str)

                if detect_gaps and inst in last_timestamp:
                    prev_dt = last_timestamp[inst]
                    if _is_business_day_gap(prev_dt, curr_dt):
                        report.quarantined.append({
                            "row": row,
                            "reason": f"Session gap: {prev_dt.date()} -> {curr_dt.date()}",
                        })
                        continue

                if detect_intraday_gaps and inst in last_timestamp:
                    prev_dt = last_timestamp[inst]
                    if prev_dt.date() == curr_dt.date():
                        diff_sec = (curr_dt - prev_dt).total_seconds()
                        max_sec = expected_bar_interval_minutes * 60 * 5
                        if diff_sec > max_sec:
                            report.quarantined.append({
                                "row": row,
                                "reason": f"Intraday gap: {prev_dt.strftime('%H:%M')} -> {curr_dt.strftime('%H:%M')}",
                            })
                            continue

                last_timestamp[inst] = curr_dt

                good.append(result)
                report.passed += 1

    return report, good
