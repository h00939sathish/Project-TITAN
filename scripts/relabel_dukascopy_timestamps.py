"""Relabel 1m bars whose timestamp minute was stamped from the bar ordinal.

`pull_dukascopy_1m.py` used to write each bar's timestamp from its index in the
hour's bar list instead of the bar's true minute, so a sparse hour was
compacted (minutes 0, 1, 2...) and the labels no longer matched the market.
The true minute was always stored in the bar's `minute` field, so the
correction is exact and needs no re-fetch: rebuild the timestamp from `minute`
and verify the sequence stays strictly increasing.

The volume-source diagnostic cites the output of this relabel ("corrected"
tick files) by SHA-256; keep the serialization byte-stable or update those
hashes with the evidence.

Run: python scripts/relabel_dukascopy_timestamps.py \
        --dir research/dukascopy_1m_ba --out research/dukascopy_1m_ba_corrected
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "research" / "dukascopy_1m_ba"
SYMBOLS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")


def relabel(rows: list[dict], symbol: str = "?") -> tuple[list[dict], int]:
    """Return (relabelled rows, count changed). Raises on a non-monotonic result."""
    out: list[dict] = []
    prev: str | None = None
    fixed = 0
    for row in rows:
        minute = row.get("minute")
        if not isinstance(minute, int) or not 0 <= minute <= 59:
            raise ValueError(f"{symbol}: bar minute {minute!r} is not 0..59")
        ts = row["timestamp"]
        corrected = f"{ts[:14]}{minute:02d}:00Z"
        if prev is not None and not corrected > prev:
            raise ValueError(
                f"{symbol}: relabel is not strictly increasing at {ts} -> {corrected}")
        prev = corrected
        if corrected != ts:
            fixed += 1
        out.append({**row, "timestamp": corrected})
    return out, fixed


def serialize(rows: list[dict]) -> str:
    # Compact separators: matches the byte-stable copies cited in
    # research/evidence/volume_source_20261029/.
    return json.dumps(rows, separators=(",", ":"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--out", default=None,
                    help="output directory; omitted means report only")
    args = ap.parse_args()
    src_dir = Path(args.dir)
    out_dir = Path(args.out) if args.out else None
    for sym in SYMBOLS:
        path = src_dir / f"{sym}.json"
        if not path.exists():
            print(f"{sym}: absent, skipped")
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        corrected, fixed = relabel(rows, sym)
        text = serialize(corrected)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print(f"{sym}: {len(rows)} rows, {fixed} timestamps corrected, sha256 {digest}")
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{sym}.json").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
