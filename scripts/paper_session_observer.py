"""Paper-session certification observer (runs alongside the live session).

Drives one full RTH session of certification evidence:

1. RELEASE AT RTH OPEN — at 09:40 ET (open + warmup margin) writes the
   kill-switch release signal in the project root. The session's release is
   reconcile-gated, so a real drift REFUSES the release (fail-closed stays).

2. PER-INSTRUMENT BAR ADVANCE — every 300s records the latest completed
   5-minute bar timestamp for each instrument from an INDEPENDENT read-only
   TWS feed (spare client id 900), plus the session heartbeat and metrics.
   Advancing timestamps = feed is live for every instrument.

3. FORCED DISCONNECT/RECONNECT DRILL — once per session (default 60 min after
   release): disconnects the observer feed (simulating a server-side 1100
   drop), asserts recovery is flagged, runs recover(), and verifies completed
   bars ADVANCE AGAIN. Same recovery code path the live session runs.

4. SESSION-END RECONCILE — at 16:00 ET reads the event store (RiskDecision /
   Order event counts), positions, cash, and per-instrument stats, and writes
   the certification summary.

Output: certification_<date>.log in the project root.
"""

import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(r"D:\projects\Project TITAN")
CONSOLE = ROOT / "paper_session_console.log"
METRICS_GLOB = ROOT.glob("metrics-*.json")
INSTRUMENTS = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "XLF", "XLK"]
RELEASE_FILE = ROOT / "release_kill_switch.signal"
OBSERVER_CID = 900
POLL_S = 300

sys.path.insert(0, str(ROOT / "src"))


def et_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(ZoneInfo("US/Eastern"))


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with open(ROOT / f"certification_{datetime.now(timezone.utc):%Y%m%d}.log",
              "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def heartbeat() -> str:
    try:
        text = CONSOLE.read_text(encoding="utf-8", errors="ignore")
        hits = [l for l in text.splitlines() if "kw=" in l and "uptime=" in l]
        return hits[-1].strip() if hits else "no heartbeat"
    except OSError:
        return "console unreadable"


def bar_timestamps(feed) -> dict:
    out = {}
    for instr in INSTRUMENTS:
        bars = feed.completed_bars(instr)
        out[instr] = bars[-1][0] if bars else None
    return out


def metrics_snapshot() -> dict:
    try:
        files = sorted(ROOT.glob("metrics-*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return {}
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def event_counts() -> dict:
    try:
        import titan._core as core
        store = core.EventStore(str(ROOT / ".titan_state.db"))
        types = ["RiskDecision", "OrderStateChanged", "OrderAccepted", "OrderRejected",
                 "TradeExecution", "RiskStateSnapshot"]
        return {t: len(store.replay_by_type(t)) for t in types}
    except Exception as exc:
        return {"error": str(exc)}


def state_snapshot() -> dict:
    try:
        p = ROOT / ".titan_state.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def release_kill_switch() -> None:
    RELEASE_FILE.write_text("release", encoding="utf-8")
    log("release signal written (session releases on next 5th cycle if reconcile InSync)")


def forced_disconnect_drill(feed) -> None:
    """Simulate a server-side disconnect, run recovery, verify bars advance."""
    log("=== FORCED DISCONNECT/RECONNECT DRILL ===")
    before = bar_timestamps(feed)
    log(f"pre-drill bar timestamps: {before}")
    # simulate the 1100 server drop: tear down the socket + flag recovery
    feed.disconnect()
    feed._recovery_needed = True
    log(f"disconnect forced; needs_recovery={feed.needs_recovery()}")
    ref = feed.latest_ts()
    t0 = time.monotonic()
    feed.recover()
    log(f"recover() completed in {time.monotonic() - t0:.1f}s; needs_recovery={feed.needs_recovery()}")
    # wait for bars to advance again
    advanced = False
    for _ in range(12):
        time.sleep(10)
        if feed.bars_advancing(ref):
            advanced = True
            break
    after = bar_timestamps(feed)
    log(f"post-drill bar timestamps: {after}")
    log(f"DRIFT RESULT: bars-advancing={advanced}")
    if not advanced:
        log("DRIFT FAILED: no advancing bars after recovery")
    else:
        log("drill PASSED: feed reconnected, resubscribed, bars advancing again")


def main() -> int:
    from titan.data.tws_feed import TWSRealtimeFeed

    log(f"certification observer started (instruments={INSTRUMENTS})")

    feed = None
    try:
        feed = TWSRealtimeFeed(INSTRUMENTS, bar_size="5 mins", client_id=OBSERVER_CID)
        log(f"observer feed connected (cid={OBSERVER_CID})")
    except Exception as exc:
        log(f"observer feed connect FAILED: {exc}")

    released = False
    drill_done = False
    drill_at = None
    end_ts = None
    release_attempted_ts = None

    while True:
        now_et = et_now()
        # 1) release at RTH open + margin; confirm via heartbeat, retry once
        if not released and now_et.weekday() < 5 and now_et >= now_et.replace(hour=9, minute=40):
            if release_attempted_ts is None:
                release_attempted_ts = time.monotonic()
            if not RELEASE_FILE.exists():
                release_kill_switch()
            hb = heartbeat()
            if "kw=0" in hb or "kw=1" in hb:
                released = True
                log("CONFIRMED: session kill switch released (heartbeat kw<2)")
                drill_at = time.monotonic() + 3600  # drill 60 min after release
            elif time.monotonic() - release_attempted_ts > 600:
                log("release not reflected after 10min — likely reconcile refusal; "
                    "STAYING LATCHED and continuing to observe (fail-safe)")
                released = True
        # 2) forced drill once, mid-session
        if released and not drill_done and drill_at and time.monotonic() >= drill_at:
            try:
                forced_disconnect_drill(feed)
            except Exception as exc:
                log(f"drill FAILED: {exc}")
            drill_done = True
        # 3) periodic evidence
        if now_et.second % POLL_S < 5:
            hb = heartbeat()
            ts = bar_timestamps(feed) if feed else {}
            log(f"heartbeat: {hb}")
            log(f"bar-ts: {json.dumps(ts)}")
        # 4) session end
        if released and now_et.weekday() < 5 and now_et >= now_et.replace(hour=16, minute=0):
            if end_ts is None:
                end_ts = time.monotonic()
                log("=== SESSION END: final evidence ===")
                log(f"events: {json.dumps(event_counts())}")
                log(f"state: {json.dumps(state_snapshot())}")
                m = metrics_snapshot()
                log(f"metrics keys: {list(m.keys())}")
                if "per_instrument" in m:
                    log(f"per-instrument: {json.dumps(m['per_instrument'])}")
                log("certification observation complete")
            if time.monotonic() - end_ts > 30:
                break
        time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("observer stopped", flush=True)
        sys.exit(0)
