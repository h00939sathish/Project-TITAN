"""Unit tests for macro rate-differential ingestion (RQ-FX-001, Path A).

HTTP is mocked; the module's fail-closed contract (raise MacroDataUnavailable on
any network/HTTP/parse failure, never a silent/partial series) is what we enforce.
"""
from __future__ import annotations

from datetime import date
from unittest import mock

import pytest

from titan.data.macro_rates import (
    MacroDataUnavailable,
    RatePoint,
    fetch_ecb_series,
    rate_differential,
    est_compounded_tenor,
)

CSV_OK = (
    "KEY,FREQ,BENCHMARK_ITEM,DATA_TYPE_EST,TIME_PERIOD,OBS_VALUE,OBS_STATUS,CONF_STATUS,UNIT_MEASURE\r\n"
    "EST.B.EU000A2QQF16.CR,B,EU000A2QQF16,CR,2026-08-04,2.18,A,F,pct\r\n"
    "EST.B.EU000A2QQF16.CR,B,EU000A2QQF16,CR,2026-08-05,2.19,A,F,pct\r\n"
    "EST.B.EU000A2QQF16.CR,B,EU000A2QQF16,CR,2026-08-06,2.20,A,F,pct\r\n"
    "EST.B.SOMEOTHER.CR,B,OTHER,CR,2026-08-06,9.99,A,F,pct\r\n"
)


class _FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def ok_urlopen():
    with mock.patch("titan.data.macro_rates.urllib.request.urlopen",
                    return_value=_FakeResp(CSV_OK.encode())) as m:
        yield m


def test_ecb_parses_only_target_series_and_sorts(ok_urlopen):
    pts = fetch_ecb_series("EST.B.EU000A2QQF16.CR")
    assert [p.iso_date for p in pts] == ["2026-08-04", "2026-08-05", "2026-08-06"]
    assert pts[-1].value == 2.20
    assert pts[-1].as_of.isoformat() == "2026-08-06"
    # the URL path is dataset/inner (two segments), not one
    url = ok_urlopen.call_args.args[0].full_url
    assert url.startswith("https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2QQF16.CR?")


def test_ecb_http_error_fails_closed():
    import urllib.error
    with mock.patch("titan.data.macro_rates.urllib.request.urlopen",
                    side_effect=urllib.error.HTTPError("", 503, "down", None, None)):
        with pytest.raises(MacroDataUnavailable):
            fetch_ecb_series("EST.B.EU000A2QQF16.CR")


def test_ecb_network_error_fails_closed():
    import urllib.error
    with mock.patch("titan.data.macro_rates.urllib.request.urlopen",
                    side_effect=urllib.error.URLError("boom")):
        with pytest.raises(MacroDataUnavailable):
            fetch_ecb_series("EST.B.EU000A2QQF16.CR")


def test_ecb_empty_body_fails_closed():
    with mock.patch("titan.data.macro_rates.urllib.request.urlopen",
                    return_value=_FakeResp(b"KEY,FREQ,TIME_PERIOD,OBS_VALUE\r\n")):
        with pytest.raises(MacroDataUnavailable):
            fetch_ecb_series("EST.B.EU000A2QQF16.CR")


def test_unknown_tenor_raises_valueerror():
    with pytest.raises(ValueError):
        est_compounded_tenor("9Y")


def test_rate_differential_aligns_by_date():
    a = [RatePoint("A", d, 1.0) for d in (date(2026, 8, 5), date(2026, 8, 6))]
    b = [RatePoint("B", d, 0.5) for d in (date(2026, 8, 5), date(2026, 8, 6), date(2026, 8, 7))]
    spread = rate_differential(a, b)
    assert [(d, round(s, 2)) for d, s in spread] == [(date(2026, 8, 5), 0.5), (date(2026, 8, 6), 0.5)]


def test_rate_differential_no_aligned_dates_fails_closed():
    a = [RatePoint("A", date(2026, 8, 5), 1.0)]
    b = [RatePoint("B", date(2026, 8, 6), 0.5)]
    with pytest.raises(MacroDataUnavailable):
        rate_differential(a, b)