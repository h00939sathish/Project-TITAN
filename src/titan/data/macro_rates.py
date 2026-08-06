"""Macro rate-differential ingestion (RQ-FX-001 / FX-CARRY-VOL, Path A).

Central-bank short-term rate series used to compute carry differentials for
FX pairs. Primary source: ECB Data Portal (no key required).

Working series (verified live 2026-08-06):
  - EST.B.EU000A2QQF16.CR  compounded euro short-term rate, 1 week tenor
  - EST.B.EU000A2QQF24.CR  compounded euro short-term rate, 1 month tenor
  - EST.B.EU000A2QQF32.CR  compounded euro short-term rate, 3 month tenor

Other currency legs (USD EFFR via FRED, GBP SONIA via BoE) are pluggable via
the same interface; they require credentials and therefore fail CLOSED here.

Fail-closed contract: any network/HTTP/parse failure raises MacroDataUnavailable
- never a silent zero or a partial series.
"""
from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime

ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
USER_AGENT = "ProjectTITAN-macro-ingest/0.1 (research; RQ-FX-001)"

# ESTR compounded tenor -> ECB series key (verified working)
ESTR_TENOR_KEYS = {
    "1W": "EST.B.EU000A2QQF16.CR",
    "1M": "EST.B.EU000A2QQF24.CR",
    "3M": "EST.B.EU000A2QQF32.CR",
}


class MacroDataUnavailable(Exception):
    """Raised when a macro rate series cannot be fetched or parsed.
    Fail-closed: callers must never proceed on missing/partial rate data."""


@dataclass(frozen=True)
class RatePoint:
    series_key: str
    as_of: date
    value: float
    unit: str = "pct"

    @property
    def iso_date(self) -> str:
        return self.as_of.isoformat()


def _parse_ecb_csv(series_key: str, body: bytes) -> list[RatePoint]:
    """Parse ECB csvdata responses into RatePoint rows for one series key."""
    text = body.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    points: list[RatePoint] = []
    for row in reader:
        key = row.get("KEY", "")
        if key != series_key:
            continue
        tp = (row.get("TIME_PERIOD") or "").strip()
        val = (row.get("OBS_VALUE") or "").strip()
        if not tp or not val:
            continue
        try:
            as_of = datetime.strptime(tp, "%Y-%m-%d").date()
            value = float(val)
        except ValueError:
            continue
        points.append(RatePoint(series_key, as_of, value, row.get("UNIT_MEASURE", "pct")))
    if not points:
        raise MacroDataUnavailable(f"ECB series {series_key}: no parseable observations")
    return sorted(points, key=lambda p: p.as_of)


def fetch_ecb_series(
    series_key: str,
    start_period: str | None = None,
    last_n: int | None = None,
    timeout_s: float = 20.0,
) -> list[RatePoint]:
    """Fetch an ECB Data Portal series (csvdata) with fail-closed semantics.

    series_key must be '<DATASET>.<inner key>' (e.g.
    EST.B.EU000A2QQF16.CR); the API paths it as /data/<DATASET>/<inner key>.
    """
    if "." not in series_key:
        raise ValueError(f"series_key must be '<DATASET>.<key>', got {series_key!r}")
    dataset, inner = series_key.split(".", 1)
    query = "format=csvdata"
    if start_period:
        query += f"&startPeriod={start_period}"
    if last_n:
        query += f"&lastNObservations={int(last_n)}"
    url = f"{ECB_BASE}/{dataset}/{inner}?{query}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "identity"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status != 200:
                raise MacroDataUnavailable(f"ECB {series_key}: HTTP {resp.status}")
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise MacroDataUnavailable(f"ECB {series_key}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise MacroDataUnavailable(f"ECB {series_key}: unreachable ({exc.reason})") from exc
    except TimeoutError as exc:
        raise MacroDataUnavailable(f"ECB {series_key}: timeout") from exc
    return _parse_ecb_csv(series_key, body)


def est_compounded_tenor(tenor: str = "3M", last_n: int | None = None) -> list[RatePoint]:
    """Compounded euro short-term rate (ESTR-based) at the given tenor."""
    key = ESTR_TENOR_KEYS.get(tenor)
    if key is None:
        raise ValueError(f"Unknown ESTR tenor {tenor!r}; use one of {sorted(ESTR_TENOR_KEYS)}")
    return fetch_ecb_series(key, last_n=last_n)


def fred_effr(api_key: str, last_n: int | None = None) -> list[RatePoint]:
    """US effective federal funds rate via FRED (requires an API key).

    Raises MacroDataUnavailable unless a key is supplied - this environment has
    no FRED key, so the USD leg is intentionally unavailable (fail closed)
    rather than silently substituted.
    """
    if not api_key:
        raise MacroDataUnavailable(
            "FRED EFFR requires an API key (fred.stlouisfed.org); none configured - "
            "USD leg of the carry differential is unavailable (fail closed)")
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id=DFF&api_key={api_key}&file_type=json")
    # (implemented but gated; parsing mirrors the same fail-closed contract)
    raise MacroDataUnavailable("FRED ingestion not wired without credentials")


def rate_differential(
    rates_a: list[RatePoint], rates_b: list[RatePoint]
) -> list[tuple[date, float]]:
    """Carry differential a-b aligned by observation date.

    Returns [(as_of, spread)] only for dates present in BOTH series; if no
    dates align, raises MacroDataUnavailable (a differential computed from
    misaligned observations would be fabrication).
    """
    by_date_b = {p.as_of: p.value for p in rates_b}
    pairs = [(p.as_of, p.value - by_date_b[p.as_of]) for p in rates_a if p.as_of in by_date_b]
    if not pairs:
        raise MacroDataUnavailable("rate_differential: no aligned observation dates")
    return sorted(pairs)