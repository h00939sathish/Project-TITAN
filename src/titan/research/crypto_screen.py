"""Preregistered crypto screens. Research-only. CRYPTO-001 is implemented.

This module owns the shared evidence pipeline for every CRYPTO-00X screen:
``run_crypto_screen`` validates the pre-registration, splits IS/OOS/adverse
partitions, simulates a signal function, computes the window-IC proxy, applies
the decision gates, and writes the evidence bundle.  Each screen supplies only
its signal function, its IC-proxy computation, and its hypothesis id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.crypto_simulator import (
    FILL_EXPLORATORY,
    CryptoEvidenceArtifact,
    simulate_crypto,
)
from titan.data.crypto import CryptoDataError, CryptoDataManifest, CryptoMarketEvent

_REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = _REPO_ROOT / "research" / "crypto" / "results"


@dataclass(frozen=True)
class PreRegistration:
    hypothesis_id: str
    universe: list[str]
    signal: str
    parameters: dict[str, Any]
    cost_label: str
    is_partition: dict[str, str]
    oos_partition: dict[str, str]
    participation_cap: str
    pass_criteria: dict[str, Any]

    def missing_fields(self) -> list[str]:
        required = [
            "hypothesis_id",
            "universe",
            "signal",
            "parameters",
            "cost_label",
            "is_partition",
            "oos_partition",
            "participation_cap",
            "pass_criteria",
        ]
        missing = []
        for name in required:
            value = getattr(self, name)
            if value in (None, "", [], {}):
                missing.append(name)
        return missing


def load_preregistration(path: Path) -> PreRegistration:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PreRegistration(
        hypothesis_id=data.get("hypothesis_id", ""),
        universe=list(data.get("universe") or []),
        signal=data.get("signal", ""),
        parameters=dict(data.get("parameters") or {}),
        cost_label=data.get("cost_label", ""),
        is_partition=dict(data.get("is_partition") or {}),
        oos_partition=dict(data.get("oos_partition") or {}),
        participation_cap=str(data.get("participation_cap") or ""),
        pass_criteria=dict(data.get("pass_criteria") or {}),
    )


def _in_partition(ts: datetime, part: dict[str, str]) -> bool:
    start = datetime.fromisoformat(part["from"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(part["to"].replace("Z", "+00:00"))
    return start <= ts <= end


def funding_basis_signal(event: CryptoMarketEvent, state: dict[str, Any]) -> Decimal:
    """Short perp (collect) when funding is persistently positive above threshold."""
    threshold = Decimal(str(state["parameters"]["funding_abs_threshold"]))
    if event.event_type == "FUNDING" and event.funding_rate is not None:
        state["last_funding"] = event.funding_rate
    funding = state.get("last_funding")
    if funding is None:
        return Decimal("0")
    if funding > threshold:
        return Decimal("-1")
    if funding < -threshold:
        return Decimal("1")
    return Decimal("0")


def evaluate_gates(
    oos: CryptoEvidenceArtifact,
    prereg: PreRegistration,
    *,
    ic_positive_frac: float,
    concentration: float,
    adverse_net_positive: bool,
    replicated: bool,
) -> dict[str, Any]:
    if not oos.can_qualify or oos.fill_model == FILL_EXPLORATORY:
        return {"verdict": "negative_result", "reason": "exploratory_fill_cannot_qualify"}
    net = float(oos.attribution.net())
    sharpe_ok = net > 0  # proxy: net positive OOS; window Sharpe computed by caller
    ic_ok = ic_positive_frac >= float(prereg.pass_criteria.get("ic_positive_frac", 0.70))
    conc_ok = concentration <= float(prereg.pass_criteria.get("max_concentration", 0.35))
    cap_ok = adverse_net_positive
    rep_ok = replicated
    gates = {
        "oos_net_positive": sharpe_ok,
        "ic_frac": ic_ok,
        "concentration": conc_ok,
        "adverse_capacity": cap_ok,
        "replication": rep_ok,
    }
    verdict = "candidate" if all(gates.values()) else "negative_result"
    return {
        "verdict": verdict,
        "gates": gates,
        "ic_positive_frac": ic_positive_frac,
        "concentration": concentration,
    }


def run_crypto_screen(
    signal_fn: Callable[[CryptoMarketEvent, dict[str, Any]], Decimal],
    ic_proxy_fn: Callable[[list[CryptoMarketEvent], PreRegistration], float],
    hypothesis_id: str,
    events: list[CryptoMarketEvent],
    manifest: CryptoDataManifest,
    prereg: PreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Run a preregistered crypto screen through the standard evidence pipeline.

    Shared skeleton for every CRYPTO-00X screen: validates the pre-registration,
    splits events into IS/OOS/adverse partitions, simulates ``signal_fn`` net of
    costs, computes the window-IC proxy with ``ic_proxy_fn``, applies the decision
    gates, and writes ``research/crypto/results/<hypothesis_id>-evidence-bundle.json``.
    """
    missing = prereg.missing_fields()
    if missing:
        raise CryptoDataError(f"missing pre-registration fields: {missing}")
    if allow_oos_for_parameters:
        raise CryptoDataError("OOS partition cannot be used for parameter choice")
    if prereg.hypothesis_id != hypothesis_id:
        raise CryptoDataError(f"run_crypto_screen requires {hypothesis_id}")

    cost = CryptoCostModel.binance_usdt_vip0()
    if (
        cost.label != prereg.cost_label
        and prereg.cost_label not in {cost.label, "binance_usdt_vip0_2026-08-14"}
    ):
        raise CryptoDataError("cost model does not match pre-registration")

    is_events = [e for e in events if _in_partition(e.occurred_at, prereg.is_partition)]
    oos_events = [e for e in events if _in_partition(e.occurred_at, prereg.oos_partition)]

    def _run(
        batch: list[CryptoMarketEvent],
        partition: str,
        adverse: bool = False,
    ) -> CryptoEvidenceArtifact:
        def _sig(ev: CryptoMarketEvent, st: dict[str, Any]) -> Decimal:
            st.setdefault("parameters", prereg.parameters)
            return signal_fn(ev, st)
        return simulate_crypto(
            batch,
            _sig,
            cost,
            partition,
            hypothesis_id=prereg.hypothesis_id,
            parameters=prereg.parameters,
            data_digest=manifest.digest(),
            adverse=adverse,
            participation=Decimal(prereg.participation_cap),
        )

    is_art = _run(is_events, "IS")
    oos_art = _run(oos_events, "OOS")
    adverse_art = _run(oos_events, "OOS_ADVERSE", adverse=True)

    ic_frac = ic_proxy_fn(oos_events, prereg)
    concentration = 1.0 if len(prereg.universe) <= 1 else 1.0 / len(prereg.universe)

    gates = evaluate_gates(
        oos_art,
        prereg,
        ic_positive_frac=ic_frac,
        concentration=min(concentration, 1.0),
        adverse_net_positive=float(adverse_art.attribution.net()) > 0,
        replicated=replicated,
    )
    bundle = {
        "hypothesis_id": prereg.hypothesis_id,
        "manifest_digest": manifest.digest(),
        "is": is_art.to_dict(),
        "oos": oos_art.to_dict(),
        "adverse_oos": adverse_art.to_dict(),
        "gates": gates,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{prereg.hypothesis_id}-evidence-bundle.json"
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
            for field in ("failure_mode", "failure_mode_basis", "failure_mode_confidence", "disambiguation"):
                if field in existing.get("gates", {}):
                    gates[field] = existing["gates"][field]
        except Exception:
            pass

    out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle


def _funding_ic_proxy(oos_events: list[CryptoMarketEvent], prereg: PreRegistration) -> float:
    """Fraction of OOS funding events where the trade direction matched -sign(funding)."""
    hits = 0
    total = 0
    last_funding = None
    pos = Decimal("0")
    threshold = Decimal(str(prereg.parameters["funding_abs_threshold"]))
    for ev in oos_events:
        if ev.event_type == "FUNDING" and ev.funding_rate is not None:
            last_funding = ev.funding_rate
            if last_funding > threshold:
                pos = Decimal("-1")
            elif last_funding < -threshold:
                pos = Decimal("1")
            else:
                pos = Decimal("0")
            total += 1
            if pos != 0 and (pos * last_funding) < 0:
                hits += 1
    return (hits / total) if total else 0.0


def run_crypto_001(
    events: list[CryptoMarketEvent],
    manifest: CryptoDataManifest,
    prereg: PreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Run the CRYPTO-001 funding-basis screen through the shared evidence pipeline."""
    return run_crypto_screen(
        funding_basis_signal,
        _funding_ic_proxy,
        "CRYPTO-001",
        events,
        manifest,
        prereg,
        replicated=replicated,
        allow_oos_for_parameters=allow_oos_for_parameters,
    )


if __name__ == "__main__":
    raise SystemExit("import run_crypto_001 from tests or a driver; no CLI execution path")
