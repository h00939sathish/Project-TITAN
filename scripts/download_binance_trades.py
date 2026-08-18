"""Download public Binance Vision trade/aggTrade archives for high-frequency order flow.

Writes into research/crypto/data/trades/ (gitignored). Updates checksums in
research/crypto/data/checksums_trades.json; does not rewrite frozen partition dates.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "research" / "crypto" / "data" / "trades"
BASE = "https://data.binance.vision/data/futures/um/daily/aggTrades"

SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def date_range(start: date, end: date) -> list[str]:
    out = []
    curr = start
    while curr <= end:
        out.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"skip {url}: {exc}", file=sys.stderr)
        if dest.exists():
            dest.unlink()
        return False


def main(start_date: date | None = None, end_date: date | None = None) -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    start = start_date or date(2024, 8, 14)
    end = end_date or date(2024, 8, 20)  # Default sample sprint
    days = date_range(start, end)
    ok = 0
    fail = 0
    checksums: dict[str, str] = {}
    for symbol in SYMBOLS:
        for day in days:
            url = f"{BASE}/{symbol}/{symbol}-aggTrades-{day}.zip"
            dest = DEST / symbol / f"{symbol}-aggTrades-{day}.zip"
            if fetch(url, dest):
                checksums[str(dest.relative_to(ROOT / "research" / "crypto" / "data"))] = checksum(dest)
                ok += 1
            else:
                fail += 1
    sidecar = ROOT / "research" / "crypto" / "data" / "checksums_trades.json"
    sidecar.write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    print(f"downloaded_ok={ok} failed={fail} checksums={sidecar}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
