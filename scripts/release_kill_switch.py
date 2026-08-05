"""Signal the running TITAN session to release the kill switch.

The session watches for release_kill_switch.signal in the project root and
calls engine.release_kill_switch(), which reconciles first and REFUSES if
there is genuine drift. Safe to run any time; if the session is not halted
the release is a no-op.

Run:  python scripts/release_kill_switch.py
"""
from pathlib import Path

signal = Path(__file__).resolve().parents[1] / "release_kill_switch.signal"
signal.write_text("release", encoding="utf-8")
print(f"release signal written to {signal}")
print("session will reconcile and release within ~5s if the state is clean")
