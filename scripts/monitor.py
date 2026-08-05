"""Live pipeline monitor — tails the log, shows TradeManifests + decisions in real-time."""

import json
import os
import time
from datetime import datetime, timezone

LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DB = os.path.join(LOG_DIR, ".titan_state.db")
METRICS_FILES = sorted(
    [f for f in os.listdir(LOG_DIR) if f.startswith("metrics-") and f.endswith(".json")]
)


def tail_log(log_path: str, n_lines: int = 50):
    """Read the last n_lines of the log file."""
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r") as f:
        lines = f.readlines()
    return lines[-n_lines:]


def parse_line(line: str) -> dict | None:
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def format_entry(e: dict) -> str:
    ts = e.get("timestamp", "")[11:19] if len(e.get("timestamp", "")) > 19 else e.get("timestamp", "")
    sev = e.get("severity", "?").ljust(5)
    comp = e.get("component", "?").ljust(12)
    msg = e.get("message", "")
    payload = e.get("payload", {})
    extra = ""
    if payload:
        extra = " | " + json.dumps(payload, default=str)
    return f"{ts} [{sev}] {comp} {msg}{extra}"


def read_state() -> dict:
    try:
        from titan._core import EventStore
        store = EventStore(STATE_DB)
        events = store.replay_by_type("PortfolioState")
        if events:
            return json.loads(events[-1].payload)
    except Exception:
        pass
    return {}


def format_state(s: dict) -> str:
    lines = []
    pf = s.get("portfolio", {})
    cash = pf.get("cash", {}).get("amount", "?")
    rpnl = pf.get("realized_pnl", {}).get("amount", "0")
    lines.append(f"Cash: ${cash}  |  Realized PnL: ${rpnl}")
    positions = pf.get("positions", {})
    if positions:
        for inst, pos in positions.items():
            lines.append(f"  {inst}: {pos.get('side', '?')} qty={pos.get('quantity', 0)}")
    ic = s.get("intent_counter", 0)
    lines.append(f"Total intents: {ic}")
    return "\n".join(lines)


def read_metrics() -> dict:
    if not METRICS_FILES:
        return {}
    latest = os.path.join(LOG_DIR, METRICS_FILES[-1])
    try:
        with open(latest, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def format_health(m: dict) -> str:
    lines = []
    strategies = m.get("strategies", {})
    if strategies:
        lines.append("Strategies:")
        for sid, data in strategies.items():
            status = data.get("status", "?")
            trades = data.get("trades", 0)
            sharpe = data.get("sharpe", "?")
            lines.append(f"  {sid:20s} status={status:10s} trades={trades:4d} sharpe={sharpe}")
    return "\n".join(lines)


def watch(interval: float = 2.0):
    print("=" * 80)
    print(f"TITAN Pipeline Monitor — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 80)

    log_path = os.path.join(LOG_DIR, f"titan-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log")
    if not os.path.exists(log_path):
        log_path = os.path.join(
            LOG_DIR,
            f"titan-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log",
        )
        # fallback: pick the most recent log
        logs = sorted([f for f in os.listdir(LOG_DIR) if f.startswith("titan-") and f.endswith(".log")])
        if logs:
            log_path = os.path.join(LOG_DIR, logs[-1])

    print(f"Watching: {os.path.basename(log_path)}\n")

    known_lines = 0
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            known_lines = len(f.readlines())

    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("=" * 80)
            print(f"TITAN Pipeline Monitor — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print("=" * 80)

            # Portfolio state
            state = read_state()
            if state:
                print("\n[Portfolio]")
                print(format_state(state))

            # Metrics
            metrics = read_metrics()
            if metrics:
                print("\n[Health]")
                h = format_health(metrics)
                if h:
                    print(h)

            # Latest log lines
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    lines = f.readlines()

                new_count = len(lines) - known_lines
                if new_count > 0:
                    start = max(0, len(lines) - 30)
                    recent = lines[start:]
                    print(f"\n[Log — last {len(recent)} lines]")
                    for line in recent:
                        e = parse_line(line)
                        if e:
                            print(format_entry(e))
                    known_lines = len(lines)
                else:
                    display = lines[-15:]
                    print(f"\n[Log — last {len(display)} lines (no new data)]")
                    for line in display:
                        e = parse_line(line)
                        if e:
                            print(format_entry(e))

            # Summary
            print(f"\n--- Waiting {interval}s | Log lines: {known_lines} | Ctrl+C to stop ---")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    watch()
