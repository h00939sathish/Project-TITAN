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
from datetime import datetime, timezone

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


def validate(initialization: SessionInitialization | None,
             seen_nonces: set[str]) -> str:
    """Return "" when valid, else a structured refusal reason code."""
    if initialization is None:
        return "initialization_missing"
    if not initialization.nonce:
        return "initialization_incomplete"
    if initialization.nonce in seen_nonces:
        return "initialization_replayed"
    try:
        if _parse_ts(initialization.expiry) <= datetime.now(timezone.utc):
            return "initialization_expired"
    except ValueError:
        return "initialization_expired"
    distinct = {a.approver for a in initialization.approvers}
    if len(distinct) < 2:
        return "initialization_incomplete"
    if not initialization.rationale.strip():
        return "initialization_incomplete"
    return ""
