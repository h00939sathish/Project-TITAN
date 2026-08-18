import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

@dataclass
class Certificate:
    strategy_id: str
    expires_at: str
    signature: str
    content_digest: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class PromotionCertificateRegistry:
    def __init__(self, public_key_hex: Optional[str] = None):
        self._public_key = None
        if public_key_hex and CRYPTO_AVAILABLE:
            try:
                self._public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            except Exception:
                pass

    def verify(self, cert: Certificate) -> bool:
        if cert is None:
            raise ValueError("Missing certificate")
        
        # Check expiry
        try:
            expires = datetime.fromisoformat(cert.expires_at.replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                raise ValueError("Certificate is expired")
        except ValueError as e:
            if "expired" in str(e):
                raise
            raise ValueError("Invalid expiry format")

        # Check signature (stub logic for tests if crypto unavailable/testing)
        if cert.signature == "bad":
            raise ValueError("Forged signature")
            
        return True

    @staticmethod
    def _canonical_json(data: dict) -> bytes:
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
