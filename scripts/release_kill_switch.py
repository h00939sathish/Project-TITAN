"""Authorize a kill-switch release (ADR-019 / RISK_POLICY.md:37).

A release from HALTED requires two authorized human approvals, root-cause/scope
assessment, verified control health (engine checks reconciliation + adapter +
data-feed health at release time), and an approved remediation or rollback.
The bare signal file is only a transport hint; the ReleaseAuthorization record
written here carries the authority. The session refuses (recorded, state
untouched) on missing, expired, duplicate, or incomplete authorization.

Usage:
  python scripts/release_kill_switch.py \\
      --approver alice --approver bob \\
      --correlation ks-<id-from-trigger> \\
      --assessment "JIRA-123 root cause & scope" \\
      --remediation "rollback to v2.0.3 per INC-9" \\
      [--expiry-min 15]
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from titan.risk.release_authorization import (
    ReleaseApproval,
    ReleaseAuthorization,
    new_nonce,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Authorize a kill-switch release (ADR-019)")
    ap.add_argument("--approver", action="append", required=True,
                    help="approver handle; provide at least twice (distinct)")
    ap.add_argument("--correlation", required=True,
                    help="kill incident / trigger correlation id (engine.trigger_kill_switch)")
    ap.add_argument("--assessment", required=True,
                    help="root-cause / scope assessment reference")
    ap.add_argument("--remediation", required=True,
                    help="approved remediation or rollback reference")
    ap.add_argument("--expiry-min", type=int, default=15,
                    help="authorization lifetime in minutes (bounded expiry)")
    args = ap.parse_args()

    approvers = list(dict.fromkeys([a.strip() for a in args.approver if a.strip()]))
    if len(approvers) < 2:
        print("ERROR: need at least two DISTINCT approvers", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    auth = ReleaseAuthorization(
        correlation_id=args.correlation,
        assessment=args.assessment,
        remediation=args.remediation,
        approvers=[ReleaseApproval(a, now.isoformat()) for a in approvers],
        issued_at=now.isoformat(),
        expiry=(now + timedelta(minutes=args.expiry_min)).isoformat(),
        nonce=new_nonce(seed=args.correlation),
    )

    auth_file = ROOT / "release_kill_switch.auth.json"
    signal = ROOT / "release_kill_switch.signal"
    auth_file.write_text(auth.to_json(), encoding="utf-8")
    signal.write_text("release", encoding="utf-8")

    print(f"release AUTHORIZED: approvers={approvers} correlation={args.correlation} "
          f"expiry={auth.expiry}")
    print(f"auth record -> {auth_file}")
    print(f"signal (transport hint) -> {signal}")
    print("session will reconcile + verify health and release ONLY if the "
          "authorization is valid and the feed/adapter/reconcile predicates pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())