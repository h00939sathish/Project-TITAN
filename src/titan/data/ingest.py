"""Ingest raw CSV/Parquet market data files."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class IngestMetadata:
    source_path: str
    source_checksum: str
    ingested_at: str
    record_count: int
    schema_version: str = "1.0"


def checksum(path: str | Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: str | Path) -> list[dict]:
    """Read CSV file into a list of dicts. Returns empty list on file not found."""
    import csv
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_parquet(path: str | Path) -> list[dict]:
    """Read Parquet file into a list of dicts."""
    import pyarrow.parquet as pq
    table = pq.read_table(str(path))
    return table.to_pylist()
