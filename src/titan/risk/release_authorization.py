"""Release authorization for the kill-switch release gate (ADR-019).

RISK_POLICY.md §Kill switch: release from HALTED requires reconciliation,
root-cause/scope assessment, verified control health, approved remediation or
rollback, and **two authorized human approvals**.

This module defines the durable ``ReleaseAuthorization`` record and its
validation. The bare ``release_kill_switch.signal`` file is retained only as a
transport hint that an operator intends a release; it never authorizes one.

Validation refuses (with a reason code) on: missing, expired, duplicate
(replayed nonce), incomplete (<2 distinct approvers), or correlation-mismatched
authorization. Every accepted nonce must be persisted so replays are detected.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

MIN_APPROVERS = 2


@dataclass
class ReleaseApproval:
    approver: str
    signed_at: str  # ISO-8601


@dataclass
class ReleaseAuthorization:
    correlation_id: str          # kill incident / trigger correlation
    assessment: str              # root-cause / scope assessment reference
    remediation: str             # approved remediation or rollback reference
    approvers: list[ReleaseApproval]
    issued_at: str               # ISO-8601
    expiry: str                  # ISO-8601 (bounded window)
    nonce: str                   # replay protection

    def to_json(self) -> str:
        return json.dumps(
            {
                "correlation_id": self.correlation_id,
                "assessment": self.assessment,
                "remediation": self.remediation,
                "approvers": [{"approver": a.approver, "signed_at": a.signed_at}
                              for a in self.approvers],
                "issued_at": self.issued_at,
                "expiry": self.expiry,
                "nonce": self.nonce,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> "ReleaseAuthorization":
        d = json.loads(raw)
        approvers = [
            ReleaseApproval(a["approver"], a["signed_at"])
            for a in d.get("approvers", [])
        ]
        return cls(
            correlation_id=d.get("correlation_id", ""),
            assessment=d.get("assessment", ""),
            remediation=d.get("remediation", ""),
            approvers=approvers,
            issued_at=d.get("issued_at", ""),
            expiry=d.get("expiry", ""),
            nonce=d.get("nonce", ""),
        )


def new_nonce(seed: str = "") -> str:
    material = f"{seed}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def validate(
    auth: Optional[ReleaseAuthorization],
    kill_correlation: Optional[str],
    now_iso: Optional[str] = None,
    seen_nonces: Optional[set[str]] = None,
    min_approvers: int = MIN_APPROVERS,
) -> str:
    """Return "" if the authorization is valid, else a refusal reason code.

    Codes: release_not_authorized | authorization_expired |
    authorization_incomplete | authorization_replayed |
    authorization_mismatch
    """
    if auth is None:
        return "release_not_authorized"

    now = now_iso or datetime.now(timezone.utc).isoformat()
    if auth.expiry and auth.expiry <= now:
        return "authorization_expired"

    # Two distinct authorized approvers.
    names = {a.approver.strip() for a in auth.approvers if a.approver.strip()}
    if len(names) < min_approvers:
        return "authorization_incomplete"

    # Assessment + remediation references are mandatory.
    if not auth.assessment.strip() or not auth.remediation.strip():
        return "authorization_incomplete"

    # Nonce replay protection.
    if auth.nonce:
        if seen_nonces is not None and auth.nonce in seen_nonces:
            return "authorization_replayed"
    else:
        return "authorization_incomplete"

    # Incident / kill-trigger correlation.
    if kill_correlation and auth.correlation_id != kill_correlation:
        return "authorization_mismatch"

    return ""
