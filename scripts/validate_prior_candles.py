"""Audit the prior candle dataset; strip the bi5 vendor's weekend fill.

Two jobs. As a gate it checks any prior set for Saturday bars, whole flat days
and the per-weekday bar counts, and reports the zero-volume share -- on the
canonical set (built by pull_dukascopy_jetta.py) that share is 0.005%, and every
zero-volume bar is a genuine quiet minute. As a cleanup it can still strip
padding from the archive built by the bi5 datafeed.

The bi5 daily candle endpoint pads every closed minute with a zero-volume bar
whose price does not move -- all 1440 minutes of a Saturday, the Friday tail
after the weekly close, and the Sunday head before it. Kept in, ~29% of the
bars are flat zero-return padding, which halves realised volatility and inflates
any Sharpe computed on them. merge_candle_sides() now drops the padding at
construction, so only files written before that fix need --write.

Run: python scripts/validate_prior_candles.py [--dir PATH] [--write]
"""
import argparse
import datetime as dt
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "research" / "dukascopy_1m_ba_prior"
SYMBOLS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
WEEKDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def is_synthetic(bar: dict) -> bool:
    """Vendor padding: no volume and not a single price tick on either side."""
    return (bar["n"] == 0
            and bar["o_bid"] == bar["h_bid"] == bar["l_bid"] == bar["c_bid"]
            and bar["o_ask"] == bar["h_ask"] == bar["l_ask"] == bar["c_ask"])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _by_weekday(per_day: dict[str, int]) -> dict[str, list[int]]:
    per: dict[str, list[int]] = defaultdict(list)
    for d, n in per_day.items():
        per[WEEKDAY[dt.date.fromisoformat(d).weekday()]].append(n)
    return {wd: sorted(per[wd]) for wd in WEEKDAY if per[wd]}


def _scan(rows: list[dict]) -> tuple[dict[str, int], list[str], int, list[str]]:
    """One pass over the bars: per-day bar counts, days that never moved, zeros.

    Grouping up front matters -- checking each day against the full bar list is
    O(days x bars), which is a billion comparisons on a 1.1M-bar file.
    """
    counts: dict[str, int] = defaultdict(int)
    opens: dict[str, set] = defaultdict(set)
    zero = 0
    for r in rows:
        d = r["timestamp"][:10]
        counts[d] += 1
        if r["n"] == 0:
            zero += 1
        s = opens[d]
        if len(s) < 2:
            s.add((r["o_bid"], r["c_bid"]))
    flat = sorted(d for d, s in opens.items() if len(s) == 1 and counts[d] > 1)
    thin = sorted(d for d, n in counts.items()
                  if n < 100 and dt.date.fromisoformat(d).weekday() < 5)
    return dict(counts), flat, zero, thin


def report(sym: str, before: list[dict], after: list[dict], synthetic: int) -> None:
    span = f"{after[0]['timestamp'][:10]} -> {after[-1]['timestamp'][:10]}" if after else "EMPTY"
    print(f"\n{sym}: {len(before)} bars ({span}), {synthetic} zero-volume bars flat on "
          f"both sides")
    if not after:
        return
    counts, flat, zero, thin = _scan(after)
    for wd, counts_wd in _by_weekday(counts).items():
        med = counts_wd[len(counts_wd) // 2]
        print(f"  {wd}: {len(counts_wd)} days, bars/day min {counts_wd[0]} "
              f"med {med} max {counts_wd[-1]}")
    print(f"  zero-volume bars: {zero} ({zero / len(after):.3%})")
    if thin:
        print(f"  THIN WEEKDAY SESSIONS ({len(thin)}): "
              + ", ".join(f"{d}={counts[d]}" for d in thin))
    if any(dt.date.fromisoformat(d).weekday() == 5 for d in counts):
        raise SystemExit(f"{sym}: Saturday bars survived the filter")
    if flat:
        raise SystemExit(f"{sym}: {len(flat)} whole flat day(s) survived: {flat[:5]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="rewrite files in place")
    ap.add_argument("--dir", default=str(PRIOR))
    args = ap.parse_args()
    src_dir = Path(args.dir)
    raw_dir = src_dir / ".raw_candles"
    if args.write and src_dir.resolve() == PRIOR.resolve():
        raise SystemExit(
            "--write is for the bi5 archive only. The canonical prior set comes "
            "from scripts/pull_dukascopy_jetta.py, which never emits padding, so "
            "stripping it would delete genuine quiet minutes (10 in EURUSD).")

    for sym in SYMBOLS:
        path = src_dir / f"{sym}.json"
        if not path.exists():
            print(f"{sym}: absent, skipped")
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        kept = [r for r in rows if not is_synthetic(r)]
        report(sym, rows, kept, len(rows) - len(kept))
        if not args.write:
            continue
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw = raw_dir / f"{sym}.json"
        if not raw.exists():
            shutil.copy2(path, raw)
            print(f"  raw copy -> {raw} sha256 {_sha256(raw)[:16]}")
        path.write_text(json.dumps(kept, indent=1), encoding="utf-8")
        print(f"  wrote {len(kept)} bars, sha256 {_sha256(path)[:16]}")

    if not args.write:
        print("\n(dry run -- pass --write to rewrite)")


if __name__ == "__main__":
    main()
