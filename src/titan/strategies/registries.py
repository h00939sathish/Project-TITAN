"""Feature & Experiment registries — lightweight, hash-based version tracking."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib


# ── Experiment Registry ──────────────────────────────────────────────────────

@dataclass
class ExperimentRecord:
    experiment_id: str
    git_sha: str
    strategy_id: str
    strategy_params_hash: str
    data_version: str
    regime_detector: str = ""
    ensemble_config_hash: str = ""
    result_summary: str = ""
    timestamp: str = ""


_experiments: dict[str, ExperimentRecord] = {}


def register_experiment(
    git_sha: str, strategy_id: str, strategy_params: dict, data_version: str = "1.0",
    regime_detector: str = "", ensemble_config: dict | None = None,
) -> str:
    params_raw = ",".join(f"{k}={v}" for k, v in sorted(strategy_params.items()))
    params_hash = hashlib.sha256(params_raw.encode()).hexdigest()[:12]
    ensemble_raw = ",".join(f"{k}={v}" for k, v in sorted((ensemble_config or {}).items()))
    ensemble_hash = hashlib.sha256(ensemble_raw.encode()).hexdigest()[:12] if ensemble_raw else ""
    uid = hashlib.sha256(f"{git_sha}:{strategy_id}:{params_hash}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:12]
    rec = ExperimentRecord(
        experiment_id=uid, git_sha=git_sha, strategy_id=strategy_id,
        strategy_params_hash=params_hash, data_version=data_version,
        regime_detector=regime_detector, ensemble_config_hash=ensemble_hash,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _experiments[uid] = rec
    return uid


def get_experiment(experiment_id: str) -> ExperimentRecord | None:
    return _experiments.get(experiment_id)


def list_experiments() -> list[ExperimentRecord]:
    return list(_experiments.values())


# ── Feature Registry ─────────────────────────────────────────────────────────

@dataclass
class FeatureSet:
    feature_id: str
    version: str
    parameters: dict
    dependencies: list[str]
    checksum: str


_feature_sets: dict[str, FeatureSet] = {}


def register_feature(feature_id: str, version: str, parameters: dict, dependencies: list[str] | None = None) -> str:
    raw = f"{feature_id}:{version}:{parameters}:{dependencies or []}"
    checksum = hashlib.sha256(raw.encode()).hexdigest()[:12]
    _feature_sets[checksum] = FeatureSet(
        feature_id=feature_id, version=version,
        parameters=parameters, dependencies=dependencies or [],
        checksum=checksum,
    )
    return checksum


def get_feature(checksum: str) -> FeatureSet | None:
    return _feature_sets.get(checksum)


def get_feature_hash(strategy_params: dict) -> str:
    raw = ",".join(f"{k}={v}" for k, v in sorted(strategy_params.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
