"""Data manifest — tracks provenance from file to experiment record."""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from titan.data.ingest import checksum


@dataclass
class DataManifest:
    source_path: str
    source_checksum: str
    instrument_id: str
    date_from: str
    date_to: str
    record_count: int
    applied_adjustments: list[str]
    schema_version: str = "1.0"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def compute_digest(self) -> str:
        h = hashlib.sha256()
        for key in sorted(asdict(self).keys()):
            value = getattr(self, key)
            h.update(f"{key}={value}".encode("utf-8"))
        return h.hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @staticmethod
    def from_json(json_str: str) -> "DataManifest":
        data = json.loads(json_str)
        return DataManifest(**data)

    @staticmethod
    def create_from_bars(
        bars: list[dict],
        source_path: str,
        adjustments: list[str] | None = None,
    ) -> "DataManifest":
        if not bars:
            return DataManifest(
                source_path=source_path,
                source_checksum=checksum(source_path),
                instrument_id="",
                date_from="",
                date_to="",
                record_count=0,
                applied_adjustments=adjustments or [],
            )
        timestamps = sorted(b["timestamp"] for b in bars)
        return DataManifest(
            source_path=source_path,
            source_checksum=checksum(source_path),
            instrument_id=bars[0]["instrument_id"],
            date_from=timestamps[0],
            date_to=timestamps[-1],
            record_count=len(bars),
            applied_adjustments=adjustments or [],
        )
