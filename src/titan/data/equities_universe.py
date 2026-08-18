"""Point-in-time multi-asset Equities & ETF universe loader with manifest validation.

Research-only. This module must not import execution, broker, or paper engine names.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class EquitiesDataError(ValueError):
    """Hard data quality rejection for equities universe."""


@dataclass(frozen=True)
class EquitiesUniverseManifest:
    dataset_name: str
    asset_class: str
    source: str
    universe: list[str]
    timezone: str
    calendar: str
    coverage_from: str
    coverage_to: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    fee_schedule: dict[str, float]
    retrieval_ts_utc: str
    schema_version: str = "1.0"
    checksums: dict[str, str] = field(default_factory=dict)

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "asset_class": self.asset_class,
            "source": self.source,
            "universe": list(self.universe),
            "timezone": self.timezone,
            "calendar": self.calendar,
            "coverage_from": self.coverage_from,
            "coverage_to": self.coverage_to,
            "is_partition": dict(self.is_partition),
            "oos_partition": dict(self.oos_partition),
            "fee_schedule": dict(self.fee_schedule),
            "retrieval_ts_utc": self.retrieval_ts_utc,
            "schema_version": self.schema_version,
            "checksums": dict(self.checksums),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "EquitiesUniverseManifest":
        known = {k: data[k] for k in EquitiesUniverseManifest.__dataclass_fields__ if k in data}
        return EquitiesUniverseManifest(**known)

    @staticmethod
    def load(path: str | Path) -> "EquitiesUniverseManifest":
        with open(path, encoding="utf-8") as fh:
            return EquitiesUniverseManifest.from_dict(json.load(fh))


@dataclass
class EquitiesUniverseData:
    """Aligned price and return matrices for an N-asset universe."""
    manifest: EquitiesUniverseManifest
    prices: pd.DataFrame  # Date index x Symbol columns
    returns: pd.DataFrame  # Daily simple returns

    def slice_partition(self, partition: str) -> "EquitiesUniverseData":
        if partition == "IS":
            start = self.manifest.is_partition["from"]
            end = self.manifest.is_partition["to"]
        elif partition in ("OOS", "OOS_ADVERSE"):
            start = self.manifest.oos_partition["from"]
            end = self.manifest.oos_partition["to"]
        else:
            raise EquitiesDataError(f"unknown partition {partition}")

        sliced_prices = self.prices.loc[start:end]
        sliced_returns = self.returns.loc[start:end]
        return EquitiesUniverseData(
            manifest=self.manifest,
            prices=sliced_prices,
            returns=sliced_returns,
        )


def build_equities_universe(
    symbol_series: dict[str, pd.Series],
    manifest: EquitiesUniverseManifest,
) -> EquitiesUniverseData:
    """Builds and validates an aligned price matrix from symbol price series."""
    if not symbol_series:
        raise EquitiesDataError("empty symbol series dictionary")

    # Check that all universe symbols exist
    for sym in manifest.universe:
        if sym not in symbol_series:
            raise EquitiesDataError(f"symbol {sym} in manifest not found in provided series")

    # Align into a single dataframe
    df = pd.DataFrame({sym: symbol_series[sym] for sym in manifest.universe})
    df = df.dropna(how="all")

    # Ensure index is sorted chronologically
    df = df.sort_index()

    # Forward fill small holidays/gaps, drop remaining leading NaNs
    df = df.ffill().dropna()

    if len(df) < 50:
        raise EquitiesDataError("insufficient historical bars after alignment (< 50 bars)")

    returns = df.pct_change().fillna(0.0)

    return EquitiesUniverseData(
        manifest=manifest,
        prices=df,
        returns=returns,
    )
