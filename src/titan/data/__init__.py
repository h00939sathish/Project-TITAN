"""Market data pipeline — ingest, normalize, quality, manifest, calendar, freshness."""

from .ingest import checksum, read_csv, read_parquet
from .normalize import normalize_row, ALLOWED_SYMBOLS
from .spot_metals import SPOT_METAL_SYMBOLS, spot_metal_instrument
from .quality import validate_and_quarantine, QuarantineReport
from .manifest import DataManifest
from .calendar import (
    is_trading_day,
    previous_trading_day,
    next_trading_day,
    trading_days_between,
    known_holidays,
    is_early_close,
)
from .freshness import check_freshness, coverage_days, FreshnessResult
from .approved import load_approved, ApprovedDataSource, DataSourceError

__all__ = [
    "checksum",
    "read_csv",
    "read_parquet",
    "normalize_row",
    "ALLOWED_SYMBOLS",
    "SPOT_METAL_SYMBOLS",
    "spot_metal_instrument",
    "validate_and_quarantine",
    "QuarantineReport",
    "DataManifest",
    "is_trading_day",
    "previous_trading_day",
    "next_trading_day",
    "trading_days_between",
    "known_holidays",
    "is_early_close",
    "check_freshness",
    "coverage_days",
    "FreshnessResult",
    "load_approved",
    "ApprovedDataSource",
    "DataSourceError",
]
