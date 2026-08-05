"""Explicit, operator-controlled session initialization (recovery design).

A genuinely new paper environment must never be armed implicitly by an empty
store. Startup with missing/unreadable/deleted risk state fails closed to
Triggered/Halted; reaching Armed requires an explicit, durable, audited
initialization command carrying the same authorization discipline as release:

  * two distinct approvers
  * rationale
  * bounded expiry
  * nonce replay protection
  * durable audit event on success
  * refusal on missing / incomplete / expired / replayed initialization

The initializer is an operator-controlled safety action, distinct from
ordinary startup and never triggered by an empty store.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta, timezone

@dataclass
class InitializerApproval:
    """One approver handle + signature timestamp (self-contained: this module
    must not depend on PR #4's release_authorization module)."""

    approver: str
    signed_at: str


def new_nonce(seed: str = "") -> str:
    """Fresh replay-protection nonce (unique per initialization)."""
    return f"init-{uuid.uuid4().hex[:16]}-{seed or 'anon'}"


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (any offset); lexicographic comparison is
    NOT safe across producers/offsets/precisions."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class SessionInitialization:
    approvers: list[InitializerApproval]
    rationale: str
    issued_at: str
    expiry: str
    nonce: str = field(default_factory=new_nonce)

    @classmethod
    def from_json(cls, raw: str) -> "SessionInitialization":
        data = json.loads(raw)
        return cls(
            approvers=[InitializerApproval(a["approver"], a["signed_at"])
                       for a in data.get("approvers", [])],
            rationale=data.get("rationale", ""),
            issued_at=data["issued_at"],
            expiry=data["expiry"],
            nonce=data.get("nonce", ""),
        )

    def to_json(self) -> str:
        return json.dumps({
            "approvers": [{"approver": a.approver, "signed_at": a.signed_at}
                          for a in self.approvers],
            "rationale": self.rationale,
            "issued_at": self.issued_at,
            "expiry": self.expiry,
            "nonce": self.nonce,
        })


# ADR-020: bounded expiry window. An authorization valid beyond this horizon
# (from its issued_at) is refused as unbounded — "years-long" records are not
# acceptable for a privileged safety action.
MAX_INIT_TTL_SECONDS = 24 * 3600


def validate(initialization: SessionInitialization | None,
             seen_nonces: set[str],
             authorized_approvers: Optional[set[str]] = None) -> str:
    """Return "" when valid, else a structured refusal reason code.

    Codes: initialization_missing | initialization_incomplete |
    initialization_replayed | initialization_expired |
    initialization_expiry_unbounded | initialization_unauthorized_approver

    ``authorized_approvers`` (when provided) is the registry of identities
    permitted to authorize an initialization; every asserted approver must be
    a member (RISK_POLICY two-person gate must name AUTHORIZED humans, not any
    two arbitrary strings).
    """
    if initialization is None:
        return "initialization_missing"
    if not initialization.nonce:
        return "initialization_incomplete"
    if initialization.nonce in seen_nonces:
        return "initialization_replayed"
    now_dt = datetime.now(timezone.utc)
    try:
        expiry_dt = _parse_ts(initialization.expiry)
    except ValueError:
        return "initialization_expired"
    if expiry_dt <= now_dt:
        return "initialization_expired"
    if not initialization.issued_at:
        return "initialization_incomplete"
    try:
        issued_dt = _parse_ts(initialization.issued_at)
    except ValueError:
        return "initialization_incomplete"
    # Reject future-dated authorizations (a caller could otherwise set
    # issued_at years ahead + expiry minutes later to sidestep the window),
    # allowing only a small clock-skew tolerance.
    if issued_dt > now_dt + timedelta(minutes=5):
        return "initialization_expired"
    # Bounded expiry against NOW (the record's effective window must not
    # extend far beyond validation time), not merely against its own issued_at.
    if expiry_dt > now_dt + timedelta(seconds=MAX_INIT_TTL_SECONDS):
        return "initialization_expiry_unbounded"
    # Blank/whitespace-only approver identities do NOT count as distinct.
    identities = {
        a.approver.strip()
        for a in initialization.approvers
        if a.approver and a.approver.strip()
    }
    if len(identities) < 2:
        return "initialization_incomplete"
    if authorized_approvers:
        authorized = {str(x).strip() for x in authorized_approvers}
        if not identities.issubset(authorized):
            return "initialization_unauthorized_approver"
    if not initialization.rationale.strip():
        return "initialization_incomplete"
    return ""
