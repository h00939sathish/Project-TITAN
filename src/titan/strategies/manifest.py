"""TradeManifest — full provenance for every trading decision."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import subprocess


@dataclass
class TradeManifest:
    trade_id: str
    strategy_id: str
    strategy_version: str
    params_hash: str
    instrument_id: str
    side: str
    quantity: str
    regime: dict | None = None
    ensemble: dict | None = None
    filters: dict | None = None
    risk: dict | None = None
    price: str | None = None
    timestamp: str = ""
    git_sha: str = ""


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _params_hash(params: dict) -> str:
    raw = ",".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def make_manifest(
    strategy_id: str,
    strategy_version: str,
    strategy_params: dict,
    instrument_id: str,
    side: str,
    quantity: str,
    price: str | None = None,
    regime: dict | None = None,
    ensemble: dict | None = None,
    filters: dict | None = None,
    risk: dict | None = None,
) -> TradeManifest:
    uid = hashlib.sha256(
        f"{strategy_id}:{instrument_id}:{side}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:12]
    return TradeManifest(
        trade_id=uid,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        params_hash=_params_hash(strategy_params),
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=price,
        regime=regime or {},
        ensemble=ensemble or {},
        filters=filters or {},
        risk=risk or {},
        timestamp=datetime.now(timezone.utc).isoformat(),
        git_sha=_git_sha(),
    )
