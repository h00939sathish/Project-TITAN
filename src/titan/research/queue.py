"""Nightly WF-v2 queue: run each queued hypothesis through `wf_v2.run` and log it.

The queue file is human-edited input and is never written here. A run can only
produce what `wf_v2.run` produces (a bundle and memo under research/wf_v2/results)
plus one log line per attempt. Nothing here can promote, touch live config, or
change the frozen protocol; a protocol whose hash differs from the pin aborts
the whole night before any hypothesis runs.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import tomllib
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from titan.research import wf_v2

QUEUE_FILE = "research/queue.toml"
RUN_LOG = "research/wf_v2/run_log.jsonl"
# sha256 of the protocol with CRLF normalized to LF, so Windows and Linux checkouts agree.
PINNED_PROTOCOL_SHA256 = "0576d53ea1d9ee09f36cca2b29556fd37945747ea081c88001255e5fdbf5d37c"
MAX_RUNS_CAP = 20

_ID = re.compile(r"^EXP-\d{5}$")
_TOP_KEYS = {"max_runs_per_night", "experiment"}
_ENTRY_KEYS = {"id", "note"}


class QueueError(ValueError):
    pass


@dataclass
class QueueReport:
    status: str  # OK | ERRORS | ABORTED
    lines: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return {"OK": 0, "ERRORS": 1}.get(self.status, 3)


def load_queue(root: Path) -> tuple[list[str], int]:
    """Return (experiment ids in order, max runs per night); reject anything malformed."""
    path = root / QUEUE_FILE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise QueueError(f"{QUEUE_FILE} not found") from None
    except tomllib.TOMLDecodeError as exc:
        raise QueueError(f"{QUEUE_FILE}: {exc}") from None

    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise QueueError(f"{QUEUE_FILE}: unknown keys {sorted(unknown)}")
    max_runs = data.get("max_runs_per_night", 5)
    if not isinstance(max_runs, int) or isinstance(max_runs, bool) or not 1 <= max_runs <= MAX_RUNS_CAP:
        raise QueueError(f"max_runs_per_night must be an integer in 1..{MAX_RUNS_CAP}")

    ids: list[str] = []
    for i, entry in enumerate(data.get("experiment", []), 1):
        if not isinstance(entry, dict):
            raise QueueError(f"experiment #{i} must be a table")
        extra = set(entry) - _ENTRY_KEYS
        if extra:
            raise QueueError(f"experiment #{i}: unknown keys {sorted(extra)}")
        exp_id = entry.get("id")
        if not isinstance(exp_id, str) or not _ID.match(exp_id):
            raise QueueError(f"experiment #{i}: id must look like EXP-00042, got {exp_id!r}")
        if exp_id in ids:
            raise QueueError(f"experiment {exp_id} is queued twice")
        ids.append(exp_id)
    return ids, max_runs


def _git_head(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def append_log(root: Path, record: dict) -> None:
    path = root / RUN_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def log_outcome(root: Path, *, trigger: str, exp_id: str, check_only: bool, started: float,
                outcome: wf_v2.Outcome | None = None, error: str | None = None,
                protocol_sha256: str | None = None) -> dict:
    """Append one run record. Every attempt is logged, including refusals and crashes."""
    rel = lambda p: p.relative_to(root).as_posix() if p else None  # noqa: E731
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigger": trigger,
        "exp_id": exp_id,
        "mode": "check" if check_only else "run",
        "status": outcome.status if outcome else "ERROR",
        "exit_code": outcome.exit_code if outcome else 3,
        "reasons": list(outcome.reasons) if outcome else [],
        "error": error,
        "bundle": rel(outcome.bundle_path) if outcome else None,
        "memo": rel(outcome.memo_path) if outcome else None,
        "duration_s": round(time.monotonic() - started, 3),
        "git_head": _git_head(root),
        "protocol_sha256": protocol_sha256,
    }
    append_log(root, record)
    return record


def protocol_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_queue(root: Path = wf_v2.REPO_ROOT, *, check_only: bool = False,
              trigger: str = "queue") -> QueueReport:
    protocol = root / wf_v2.PROTOCOL
    actual = protocol_digest(protocol)
    if actual != PINNED_PROTOCOL_SHA256:
        started = time.monotonic()
        msg = (f"frozen protocol {wf_v2.PROTOCOL} hash {actual} != pinned "
               f"{PINNED_PROTOCOL_SHA256}; refusing to run any hypothesis")
        log_outcome(root, trigger=trigger, exp_id="*", check_only=check_only, started=started,
                    error=msg, protocol_sha256=actual)
        return QueueReport("ABORTED", [msg])

    try:
        ids, max_runs = load_queue(root)
    except QueueError as exc:
        log_outcome(root, trigger=trigger, exp_id="*", check_only=check_only,
                    started=time.monotonic(), error=str(exc), protocol_sha256=actual)
        return QueueReport("ABORTED", [str(exc)])

    lines = [f"queue: {len(ids)} queued, running {min(len(ids), max_runs)}"
             + (" (check only)" if check_only else "")]
    status = "OK"
    for exp_id in ids[:max_runs]:
        started = time.monotonic()
        try:
            outcome = wf_v2.run(exp_id, root=root, check_only=check_only)
        except Exception as exc:  # one broken hypothesis must not stop the night
            err = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            log_outcome(root, trigger=trigger, exp_id=exp_id, check_only=check_only,
                        started=started, error=err, protocol_sha256=actual)
            lines.append(f"{exp_id}: ERROR {err}")
            status = "ERRORS"
            continue
        log_outcome(root, trigger=trigger, exp_id=exp_id, check_only=check_only,
                    started=started, outcome=outcome, protocol_sha256=actual)
        lines.append(outcome.report)
    for exp_id in ids[max_runs:]:
        lines.append(f"{exp_id}: deferred (over max_runs_per_night={max_runs})")
    return QueueReport(status, lines)
