"""Dataset Contract — versioned, immutable dataset definition."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class DatasetContract:
    """Immutable contract defining a dataset's provenance and shape.

    This is the ground truth for every experiment. If the source data
    changes (new adjustments, different symbol), you create a new contract
    with a new version. Experiments pin to a specific contract.
    """

    id: str                                  # e.g. "spy_daily_v1"
    symbol: str
    frequency: Literal["1min", "5min", "15min", "1h", "1D", "1W", "1M"]
    adjusted: bool
    timezone: str
    source: str                              # e.g. "Polygon", "Yahoo", "TWS"
    start: date
    end: date
    survivorship_bias: bool = False
    lookahead_safe: bool = True
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    columns: tuple[str, ...] = ("open", "high", "low", "close", "volume")

    @property
    def fingerprint(self) -> str:
        """Short hash uniquely identifying this dataset version."""
        raw = f"{self.id}|{self.symbol}|{self.frequency}|{self.source}|{self.start}|{self.end}".encode()
        return hashlib.sha256(raw).hexdigest()[:12]

    def validate_path(self, base_dir: str | Path) -> Path:
        """Return the expected path for this dataset's parquet/csv file."""
        base = Path(base_dir)
        return base / f"{self.id}.csv"

    @staticmethod
    def from_csv(
        path: str | Path,
        id: str,
        symbol: str,
        frequency: Literal["1min", "5min", "15min", "1h", "1D", "1W", "1M"] = "1D",
        source: str = "local",
        timezone: str = "America/New_York",
        adjusted: bool = True,
    ) -> tuple[DatasetContract, list[dict]]:
        """Load a CSV and infer its contract from the data."""
        import csv
        path = Path(path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        dates = [r["date"] for r in rows]
        start = date.fromisoformat(dates[0])
        end = date.fromisoformat(dates[-1])
        columns = tuple(k for k in rows[0].keys() if k != "date")
        contract = DatasetContract(
            id=id, symbol=symbol, frequency=frequency,
            adjusted=adjusted, timezone=timezone, source=source,
            start=start, end=end, columns=columns,
        )
        return contract, rows
