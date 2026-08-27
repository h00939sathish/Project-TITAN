import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    class InvalidSignature(Exception):
        pass

@dataclass
class Certificate:
    strategy_id: str
    expires_at: str
    signature: str
    content_digest: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    # Optional single-use token bound into the signature. When present the
    # execution engine rejects replay of the same nonce (P0 A1).
    nonce: Optional[str] = None

class PromotionCertificateRegistry:
    def __init__(self, public_key_hex: Optional[Union[str, bytes, Any]] = None):
        self._public_key = None
        if public_key_hex is not None:
            self._public_key = self._parse_public_key(public_key_hex)

    @staticmethod
    def _parse_public_key(key_input: Any) -> Optional[Any]:
        if not CRYPTO_AVAILABLE or key_input is None:
            return None
        if isinstance(key_input, ed25519.Ed25519PublicKey):
            return key_input
        if isinstance(key_input, bytes):
            if len(key_input) == 32:
                return ed25519.Ed25519PublicKey.from_public_bytes(key_input)
            elif len(key_input) == 64:
                try:
                    return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_input.decode("ascii")))
                except Exception:
                    pass
        if isinstance(key_input, str):
            key_str = key_input.strip()
            try:
                key_bytes = bytes.fromhex(key_str)
                if len(key_bytes) == 32:
                    return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)
            except Exception:
                pass
        return None

    def verify(self, cert: Certificate, public_key: Optional[Union[str, bytes, Any]] = None) -> bool:
        if cert is None:
            raise ValueError("Missing certificate")
        
        # Check expiry
        if not cert.expires_at or not isinstance(cert.expires_at, str):
            raise ValueError("Invalid expiry format")
        try:
            expires = datetime.fromisoformat(cert.expires_at.replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                raise ValueError("Certificate is expired")
        except ValueError as e:
            if "expired" in str(e):
                raise
            raise ValueError("Invalid expiry format")

        pub = self._parse_public_key(public_key) if public_key is not None else self._public_key
        if pub is None:
            raise ValueError("Forged signature: no public key configured for verification")

        if not cert.signature or not isinstance(cert.signature, str):
            raise ValueError("Forged signature: missing or invalid signature")

        try:
            sig_bytes = bytes.fromhex(cert.signature.strip())
            if len(sig_bytes) != 64:
                raise ValueError("Forged signature: invalid signature length")
        except Exception as e:
            raise ValueError("Forged signature: invalid hex encoding") from e

        payload = {
            "strategy_id": cert.strategy_id,
            "expires_at": cert.expires_at,
            "content_digest": cert.content_digest,
            "parameters": cert.parameters,
        }
        # Nonce participates in the signature ONLY when present, so
        # certificates issued before the field existed still verify.
        if getattr(cert, "nonce", None):
            payload["nonce"] = cert.nonce
        payload_bytes = self._canonical_json(payload)

        try:
            pub.verify(sig_bytes, payload_bytes)
        except InvalidSignature as e:
            raise ValueError("Forged signature: Ed25519 verification failed") from e
        except Exception as e:
            raise ValueError("Forged signature") from e

        return True

    @staticmethod
    def _canonical_json(data: dict) -> bytes:
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def create_signed_certificate(
    private_key: Any,
    strategy_id: str,
    expires_at: str,
    content_digest: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    nonce: Optional[str] = None,
) -> Certificate:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library is required for create_signed_certificate")

    if isinstance(private_key, str):
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key.strip()))
    elif isinstance(private_key, bytes):
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
    elif not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise TypeError("private_key must be Ed25519PrivateKey, bytes, or hex string")

    payload = {
        "strategy_id": strategy_id,
        "expires_at": expires_at,
        "content_digest": content_digest,
        "parameters": parameters,
    }
    # Mirror verify(): the nonce is bound into the signature only when present.
    if nonce:
        payload["nonce"] = nonce
    payload_bytes = PromotionCertificateRegistry._canonical_json(payload)
    sig_bytes = private_key.sign(payload_bytes)
    return Certificate(
        strategy_id=strategy_id,
        expires_at=expires_at,
        signature=sig_bytes.hex(),
        content_digest=content_digest,
        parameters=parameters,
        nonce=nonce or None,
    )


def execution_scope_parameters(
    instrument: str,
    side: str,
    max_quantity: int,
    account: str,
    order_types: Optional[list] = None,
) -> Dict[str, Any]:
    """Execution-scope parameter block required by the engine's submit gate.

    The engine hard-rejects intents whose certificate lacks these bindings
    (P0 A1): a certificate authorizes a bounded execution scope, not merely a
    strategy identity."""
    scope: Dict[str, Any] = {
        "instrument": str(instrument),
        "side": str(side).upper(),
        "max_quantity": int(max_quantity),
        "account": str(account),
    }
    if order_types is not None:
        scope["order_types"] = [str(t).upper() for t in order_types]
    return scope
