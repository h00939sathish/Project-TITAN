"""Offline timestamp regression tests using the real tick aggregator."""

import os
import socket
import subprocess
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from scripts import pull_dukascopy_1m as downloader

DAY = date(2025, 8, 1)
QUOTES = (
    (0, 1.1002, 1.1000),
    (1_000, 1.1006, 1.1004),
    (30_000, 1.1001, 1.0999),
    (59_999, 1.1003, 1.1001),
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        # pytest.fail is not swallowed by the downloader's except Exception.
        pytest.fail("Network/subprocess use is forbidden in offline timestamp tests")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


@pytest.fixture
def pull_day(monkeypatch, tmp_path):
    def run(hours):
        fetched = []

        def fetch_hour(url, destination):
            hour = int(url.rsplit("/", 1)[1].split("h_ticks.bi5")[0])
            assert Path(destination) == tmp_path / "20250801" / f"{hour:02d}.bi5"
            fetched.append(hour)
            return hours.get(hour, ("closed", []))

        monkeypatch.setattr(downloader, "fetch_hour", fetch_hour)
        result = downloader._pull_one_day("EURUSD", DAY, tmp_path)
        assert sorted(fetched) == list(range(24))
        return result

    return run


def ticks_for(minutes):
    # fetch_hour supplies accepted records; aggregation and its counts stay real.
    return [
        (minute * 60_000 + offset, ask, bid)
        for minute in minutes
        for offset, ask, bid in QUOTES
    ]


def expected_bar(hour, minute):
    return {
        "timestamp": f"2025-08-01T{hour:02d}:{minute:02d}:00Z",
        "minute": minute,
        "o_ask": 1.1002,
        "h_ask": 1.1006,
        "l_ask": 1.1001,
        "c_ask": 1.1003,
        "o_bid": 1.1000,
        "h_bid": 1.1004,
        "l_bid": 1.0999,
        "c_bid": 1.1001,
        "n": 4,
    }


@pytest.mark.parametrize("hour, minutes", [
    pytest.param(0, (2,), id="nonzero-first-minute"),
    pytest.param(0, (0, 2, 7), id="interior-gaps"),
    pytest.param(13, (2, 17, 59), id="sparse-nonzero-hour-minute-59"),
    pytest.param(23, (59,), id="last-minute-of-day"),
    pytest.param(0, tuple(range(60)), id="contiguous-midnight-hour"),
    pytest.param(13, tuple(range(60)), id="contiguous-nonzero-hour"),
])
def test_pull_day_uses_actual_minutes_and_preserves_bar_fields(pull_day, hour, minutes):
    ticks = ticks_for(minutes)

    bars, conn_fail = pull_day({hour: ("ok", ticks)})

    assert conn_fail == 0
    expected = [expected_bar(hour, minute) for minute in minutes]
    assert [bar["timestamp"] for bar in bars] == [bar["timestamp"] for bar in expected]
    assert bars == expected
    assert sum(bar["n"] for bar in bars) == len(ticks)


def test_empty_hour_between_populated_hours_emits_no_bar(pull_day):
    morning = ticks_for((2,))
    afternoon = ticks_for((59,))

    bars, conn_fail = pull_day({
        12: ("ok", morning),
        13: ("ok", []),
        14: ("ok", afternoon),
    })

    assert conn_fail == 0
    # Cross-hour completion order is intentionally unconstrained.
    ordered = sorted(bars, key=lambda bar: bar["timestamp"])
    assert [bar["timestamp"] for bar in ordered] == [
        "2025-08-01T12:02:00Z", "2025-08-01T14:59:00Z",
    ]
    assert ordered == [expected_bar(12, 2), expected_bar(14, 59)]
    assert sum(bar["n"] for bar in bars) == len(morning) + len(afternoon)


@pytest.mark.parametrize("kind", ["closed", "ok"])
def test_empty_day_has_no_bars_or_connection_failures(pull_day, kind):
    bars, conn_fail = pull_day({hour: (kind, []) for hour in range(24)})

    assert bars == []
    assert conn_fail == 0
