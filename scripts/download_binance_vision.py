"""Download public Binance Vision monthly files. No API key.

Writes into research/crypto/data/ (gitignored). Updates checksums in a
sidecar JSON; does not rewrite the frozen partition dates.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "research" / "crypto" / "data"
BASE = "https://data.binance.vision/data"

SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def months(start: date, end: date) -> list[str]:
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:  # noqa: BLE001 — download is best-effort per file
        print(f"skip {url}: {exc}", file=sys.stderr)
        if dest.exists():
            dest.unlink()
        return False


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    span = months(date(2024, 8, 1), date(2026, 8, 1))
    ok = 0
    fail = 0
    checksums: dict[str, str] = {}
    for symbol in SYMBOLS:
        for month in span:
            paths = [
                (
                    f"{BASE}/spot/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip",
                    DEST / "spot" / symbol / f"{symbol}-1h-{month}.zip",
                ),
                (
                    f"{BASE}/futures/um/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip",
                    DEST / "um" / symbol / f"{symbol}-1h-{month}.zip",
                ),
                (
                    f"{BASE}/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip",
                    DEST / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip",
                ),
            ]
            for url, dest in paths:
                if fetch(url, dest):
                    checksums[str(dest.relative_to(DEST))] = checksum(dest)
                    ok += 1
                else:
                    fail += 1
    sidecar = DEST / "checksums.json"
    sidecar.write_text(__import__("json").dumps(checksums, indent=2), encoding="utf-8")
    print(f"downloaded_ok={ok} failed={fail} checksums={sidecar}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
