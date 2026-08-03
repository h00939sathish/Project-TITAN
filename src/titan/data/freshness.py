"""Freshness and staleness checks for market data."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from titan.data.calendar import previous_trading_day, is_trading_day
from titan.data.manifest import DataManifest


@dataclass
class FreshnessResult:
    fresh: bool
    last_bar_date: date | None
    expected_last_date: date | None
    trading_days_stale: int | None
    reason: str = ""


def check_freshness(
    manifest: DataManifest,
    reference_date: date | None = None,
    max_stale_trading_days: int = 2,
) -> FreshnessResult:
    if not manifest.date_to:
        return FreshnessResult(
            fresh=False,
            last_bar_date=None,
            expected_last_date=None,
            trading_days_stale=None,
            reason="Manifest has no date_to — no data",
        )

    try:
        last_bar = date.fromisoformat(manifest.date_to[:10])
    except (ValueError, TypeError):
        return FreshnessResult(
            fresh=False,
            last_bar_date=None,
            expected_last_date=None,
            trading_days_stale=None,
            reason=f"Cannot parse date_to: {manifest.date_to}",
        )

    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    max_possible = previous_trading_day(reference_date)

    if max_possible <= last_bar:
        return FreshnessResult(
            fresh=True,
            last_bar_date=last_bar,
            expected_last_date=max_possible,
            trading_days_stale=0,
            reason="Data is current",
        )

    stale_days = 0
    d = max_possible
    while d > last_bar:
        if is_trading_day(d):
            stale_days += 1
        d -= timedelta(days=1)

    if stale_days <= max_stale_trading_days:
        return FreshnessResult(
            fresh=True,
            last_bar_date=last_bar,
            expected_last_date=max_possible,
            trading_days_stale=stale_days,
            reason=f"Within tolerance ({stale_days} trading days stale, max {max_stale_trading_days})",
        )

    return FreshnessResult(
        fresh=False,
        last_bar_date=last_bar,
        expected_last_date=max_possible,
        trading_days_stale=stale_days,
        reason=f"Stale by {stale_days} trading days (max allowed: {max_stale_trading_days})",
    )


def coverage_days(manifest: DataManifest) -> int:
    if not manifest.date_from or not manifest.date_to:
        return 0
    try:
        start = date.fromisoformat(manifest.date_from[:10])
        end = date.fromisoformat(manifest.date_to[:10])
        return (end - start).days
    except (ValueError, TypeError):
        return 0
