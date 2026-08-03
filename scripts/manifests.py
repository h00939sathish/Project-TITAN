"""View recent TradeManifests from the pipeline — scan logs for manifest data."""

import json
import os
import re
from collections import Counter

LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_logs():
    logs = sorted(
        [f for f in os.listdir(LOG_DIR) if f.startswith("titan-") and f.endswith(".log")]
    )
    return [os.path.join(LOG_DIR, f) for f in logs]


def extract_manifests(log_path: str) -> list[dict]:
    """Parse log lines that look like TradeManifest JSON."""
    manifests = []
    if not os.path.exists(log_path):
        return manifests
    with open(log_path, "r") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                payload = e.get("payload", {})
                # Look for manifest-like payloads (has trade_id + strategy_id)
                if isinstance(payload, dict) and "trade_id" in payload and "strategy_id" in payload:
                    manifests.append(payload)
                # Also check nested payload.manifest
                if isinstance(payload, dict) and "manifest" in payload:
                    manifests.append(payload["manifest"])
            except (json.JSONDecodeError, AttributeError):
                pass
    return manifests


def show():
    logs = find_logs()
    if not logs:
        print("No log files found.")
        return

    print(f"Scanning {len(logs)} log files...\n")
    all_manifests = []
    for lp in logs:
        all_manifests.extend(extract_manifests(lp))

    if not all_manifests:
        print("No TradeManifests found in logs. Pipeline may not be logging manifests as JSON entries yet.")
        print("Checking for structured pipeline entries instead...")
        return

    print(f"Found {len(all_manifests)} TradeManifests\n")

    # Summary stats
    strategies = Counter(m.get("strategy_id", "?") for m in all_manifests)
    sides = Counter(m.get("side", "?") for m in all_manifests)
    regimes = Counter(m.get("regime", {}).get("regime", "?") for m in all_manifests)

    print("── Strategies ──")
    for sid, count in strategies.most_common():
        print(f"  {sid:25s} {count:3d} trades")

    print("\n── Sides ──")
    for side, count in sides.most_common():
        print(f"  {side:6s} {count:3d}")

    print("\n── Regimes ──")
    for reg, count in regimes.most_common():
        print(f"  {reg:15s} {count:3d}")

    # Recent manifests
    print(f"\n── Last {min(10, len(all_manifests))} Manifests ──")
    for m in all_manifests[-10:]:
        ts = m.get("timestamp", "")[11:19] if len(m.get("timestamp", "")) > 19 else m.get("timestamp", "?")
        sid = m.get("strategy_id", "?")
        inst = m.get("instrument_id", "?")
        side = m.get("side", "?")
        qty = m.get("quantity", "?")
        regime = m.get("regime", {})
        reg = regime.get("regime", "-") if isinstance(regime, dict) else "-"
        ensemble = m.get("ensemble", {})
        escore = ensemble.get("score", "-") if isinstance(ensemble, dict) else "-"
        print(f"  {ts} {sid:20s} {inst:10s} {side:4s} qty={qty:4s} regime={reg:12s} escore={escore}")


if __name__ == "__main__":
    show()
