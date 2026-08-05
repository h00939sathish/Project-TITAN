"""Monitor the IBKR paper trading session (PID 7736)."""
import datetime, os, subprocess, sys, time
from pathlib import Path

LOG = Path(".titan_paper_monitor.log")
PAPER_PID = 7736

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")

def alive(pid: int) -> bool:
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                           capture_output=True, text=True, timeout=5)
        return len(r.stdout.strip().split("\n")) > 1
    except Exception:
        return False

if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
    log(f"Monitor started — watching PID {PAPER_PID}, interval={interval}s")
    while True:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if alive(PAPER_PID):
            log(f"OK — PID {PAPER_PID} running")
        else:
            log(f"DEAD — PID {PAPER_PID} not found")
        time.sleep(interval)
