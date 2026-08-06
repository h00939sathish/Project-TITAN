"""Test-only explicit session initialization (recovery design).

Production defaults fail closed: an engine over missing/unreadable/deleted
risk state starts Triggered/Halted and must NOT be armed implicitly. Tests
that need a tradeable engine use this explicit test-only initializer.
"""
from datetime import datetime, timedelta, timezone

from titan.risk.session_initialization import (
    InitializerApproval,
    SessionInitialization,
    new_nonce,
)


def initialize_fresh(engine) -> None:
    """Explicitly initialize ``engine`` as a brand-new session (test-only)."""
    now = datetime.now(timezone.utc)
    init = SessionInitialization(
        approvers=[
            InitializerApproval("test-approver-a", now.isoformat()),
            InitializerApproval("test-approver-b", now.isoformat()),
        ],
        rationale="test-only explicit initialization fixture",
        issued_at=now.isoformat(),
        expiry=(now + timedelta(minutes=15)).isoformat(),
        nonce=new_nonce("test"),
    )
    engine.initialize_new_session(init)


