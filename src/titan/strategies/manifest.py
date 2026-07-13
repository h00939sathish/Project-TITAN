"""Versioned strategy package manifest."""

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class StrategyManifest:
    """Immutable manifest for a strategy package."""
    package_id: str
    package_version: str
    package_digest: str = ""
    data_requirements: list[str] = field(default_factory=list)
    parameter_schema: dict[str, Any] = field(default_factory=dict)
    universe: list[str] = field(default_factory=list)
    risk_profile_version: str = "1.0"
    expiry: str = ""
    fixture_refs: list[str] = field(default_factory=list)

    def compute_digest(self) -> str:
        """Compute package digest from identity and requirements."""
        h = sha256()
        h.update(self.package_id.encode())
        h.update(self.package_version.encode())
        for req in sorted(self.data_requirements):
            h.update(req.encode())
        for sym in sorted(self.universe):
            h.update(sym.encode())
        h.update(self.risk_profile_version.encode())
        return h.hexdigest()

    def verify(self) -> bool:
        """Verify the stored digest matches computed digest."""
        if not self.package_digest:
            return False
        return self.package_digest == self.compute_digest()
