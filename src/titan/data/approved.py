"""Approved data source — validated, verified, fresh market data."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from titan.data.ingest import read_csv, checksum
from titan.data.manifest import DataManifest
from titan.data.quality import validate_and_quarantine
from titan.data.normalize import normalize_row
from titan.data.freshness import check_freshness, coverage_days


class DataSourceError(Exception):
    """Raised when an approved data source fails validation."""

    pass


@dataclass
class ApprovedDataSource:
    path: str
    instrument_id: str
    manifest: DataManifest
    bars: list[dict[str, Any]]

    def latest_bar_date(self) -> date | None:
        if not self.bars:
            return None
        return date.fromisoformat(self.bars[-1]["timestamp"][:10])

    def bar_count(self) -> int:
        return len(self.bars)

    def coverage_days(self) -> int:
        return coverage_days(self.manifest)


def load_approved(
    path: str,
    source_name: str = "csv",
    *,
    min_bar_count: int = 1,
    max_stale_trading_days: int = 2,
    require_checksum_match: bool = True,
    reference_date: date | None = None,
) -> ApprovedDataSource:
    path_obj = Path(path)
    if not path_obj.exists():
        raise DataSourceError(f"Data file not found: {path}")

    file_checksum = checksum(str(path_obj))

    raw_bars = read_csv(str(path_obj))

    report, good_bars = validate_and_quarantine(
        raw_bars,
        normalize_row,
        pass_through_unknown=True,
    )

    if len(good_bars) < min_bar_count:
        raise DataSourceError(
            f"Insufficient valid bars: {len(good_bars)} (min {min_bar_count}), "
            f"{report.quarantine_count} quarantined"
        )

    if not good_bars:
        raise DataSourceError(f"All {len(raw_bars)} records quarantined — no usable data")

    manifest = DataManifest.create_from_bars(
        good_bars,
        source_path=str(path_obj.resolve()),
        adjustments=["survivorship_pass_through"],
    )

    if require_checksum_match and manifest.source_checksum != file_checksum:
        raise DataSourceError(
            f"Checksum mismatch: manifest={manifest.source_checksum}, file={file_checksum}"
        )

    freshness = check_freshness(manifest, reference_date=reference_date, max_stale_trading_days=max_stale_trading_days)
    if not freshness.fresh:
        raise DataSourceError(
            f"Data is stale: {freshness.reason} "
            f"(last bar: {freshness.last_bar_date}, expected: {freshness.expected_last_date})"
        )

    return ApprovedDataSource(
        path=str(path_obj.resolve()),
        instrument_id=good_bars[0]["instrument_id"],
        manifest=manifest,
        bars=good_bars,
    )
