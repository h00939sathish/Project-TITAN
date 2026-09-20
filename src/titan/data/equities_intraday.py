"""Point-in-time multi-asset Equities and ETF 5-minute intraday universe loader.

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


class EquitiesIntradayDataError(ValueError):
    """Hard data quality rejection for intraday equities universe."""


@dataclass(frozen=True)
class EquitiesIntradayManifest:
    dataset_name: str
    asset_class: str
    source: str
    bar_interval: str
    timezone: str
    calendar: str
    market_open: str
    market_close: str
    bars_per_day: int
    coverage_from: str
    coverage_to: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    etf_anchors: list[str]
    universe: list[str]
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
            "bar_interval": self.bar_interval,
            "timezone": self.timezone,
            "calendar": self.calendar,
            "market_open": self.market_open,
            "market_close": self.market_close,
            "bars_per_day": self.bars_per_day,
            "coverage_from": self.coverage_from,
            "coverage_to": self.coverage_to,
            "is_partition": dict(self.is_partition),
            "oos_partition": dict(self.oos_partition),
            "etf_anchors": list(self.etf_anchors),
            "universe": list(self.universe),
            "fee_schedule": dict(self.fee_schedule),
            "retrieval_ts_utc": self.retrieval_ts_utc,
            "schema_version": self.schema_version,
            "checksums": dict(self.checksums),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "EquitiesIntradayManifest":
        known = {k: data[k] for k in EquitiesIntradayManifest.__dataclass_fields__ if k in data}
        return EquitiesIntradayManifest(**known)

    @staticmethod
    def load(path: str | Path) -> "EquitiesIntradayManifest":
        with open(path, encoding="utf-8") as fh:
            return EquitiesIntradayManifest.from_dict(json.load(fh))


@dataclass
class EquitiesIntradayUniverseData:
    """Aligned 5-minute price and return matrices for ETFs and constituent stocks."""

    manifest: EquitiesIntradayManifest
    prices: pd.DataFrame
    returns: pd.DataFrame
    etf_prices: pd.DataFrame
    stock_prices: pd.DataFrame

    def slice_partition(self, partition: str) -> "EquitiesIntradayUniverseData":
        if partition == "IS":
            start = self.manifest.is_partition["from"]
            end = self.manifest.is_partition["to"]
        elif partition in ("OOS", "OOS_ADVERSE"):
            start = self.manifest.oos_partition["from"]
            end = self.manifest.oos_partition["to"]
        else:
            raise EquitiesIntradayDataError(f"unknown partition {partition}")

        sliced_prices = self.prices.loc[start:end]
        sliced_returns = self.returns.loc[start:end]
        etf_cols = [col for col in self.manifest.etf_anchors if col in sliced_prices.columns]
        stock_cols = [col for col in self.manifest.universe if col in sliced_prices.columns]

        return EquitiesIntradayUniverseData(
            manifest=self.manifest,
            prices=sliced_prices,
            returns=sliced_returns,
            etf_prices=sliced_prices[etf_cols],
            stock_prices=sliced_prices[stock_cols],
        )


def build_intraday_universe(
    symbol_series: dict[str, pd.Series],
    manifest: EquitiesIntradayManifest,
) -> EquitiesIntradayUniverseData:
    """Builds and validates an aligned 5-minute price matrix from symbol price series."""
    if not symbol_series:
        raise EquitiesIntradayDataError("empty symbol series dictionary")

    all_symbols = list(manifest.etf_anchors) + list(manifest.universe)
    for sym in all_symbols:
        if sym not in symbol_series:
            raise EquitiesIntradayDataError(f"symbol {sym} in manifest not found in provided series")

    df = pd.DataFrame({sym: symbol_series[sym] for sym in all_symbols})
    df = df.dropna(how="all").sort_index()
    df = df.ffill().dropna()

    if len(df) < 20:
        raise EquitiesIntradayDataError("insufficient intraday bars after alignment")

    returns = df.pct_change().fillna(0.0)
    etf_cols = [col for col in manifest.etf_anchors if col in df.columns]
    stock_cols = [col for col in manifest.universe if col in df.columns]

    return EquitiesIntradayUniverseData(
        manifest=manifest,
        prices=df,
        returns=returns,
        etf_prices=df[etf_cols],
        stock_prices=df[stock_cols],
    )
