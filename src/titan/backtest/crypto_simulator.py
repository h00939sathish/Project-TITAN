"""Point-in-time 24/7 crypto simulator with cost attribution.

Exploratory bar-close constant-bps fills are labelled and cannot qualify.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Iterable

from titan.backtest.crypto_costs import CryptoCostModel
from titan.data.crypto import CryptoMarketEvent

FILL_EXPLORATORY = "exploratory_bar_close_constant_bps"
FILL_TAKER_MID = "taker_vs_mid_plus_spread"


@dataclass
class Attribution:
    price: Decimal = Decimal("0")
    funding: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    impact: Decimal = Decimal("0")
    borrow: Decimal = Decimal("0")
    partial_unfilled: Decimal = Decimal("0")
    latency: Decimal = Decimal("0")
    conversion: Decimal = Decimal("0")

    def net(self) -> Decimal:
        return (
            self.price
            + self.funding
            - self.fees
            - self.spread
            - self.impact
            - self.borrow
            - self.partial_unfilled
            - self.latency
            - self.conversion
        )

    def to_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.__dict__.items()} | {"net": str(self.net())}


@dataclass
class CryptoEvidenceArtifact:
    hypothesis_id: str
    fill_model: str
    can_qualify: bool
    partition: str
    cost_model_digest: str
    data_digest: str
    parameter_digest: str
    attribution: Attribution
    n_events: int
    n_trades: int
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "fill_model": self.fill_model,
            "can_qualify": self.can_qualify,
            "partition": self.partition,
            "cost_model_digest": self.cost_model_digest,
            "data_digest": self.data_digest,
            "parameter_digest": self.parameter_digest,
            "attribution": self.attribution.to_dict(),
            "n_events": self.n_events,
            "n_trades": self.n_trades,
            "notes": self.notes,
            "extra": self.extra,
        }


def _digest(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


SignalFn = Callable[[CryptoMarketEvent, dict[str, Any]], Decimal]


def simulate_crypto(
    events: Iterable[CryptoMarketEvent],
    signal: SignalFn,
    cost_model: CryptoCostModel,
    partition: str,
    *,
    hypothesis_id: str,
    parameters: dict[str, Any],
    data_digest: str,
    fill_model: str = FILL_TAKER_MID,
    adverse: bool = False,
    participation: Decimal = Decimal("1"),
) -> CryptoEvidenceArtifact:
    events = list(events)
    state: dict[str, Any] = {"position_perp": Decimal("0"), "position_spot": Decimal("0"), "last_mark": {}}
    attr = Attribution()
    n_trades = 0
    can_qualify = fill_model != FILL_EXPLORATORY
    notes: list[str] = []
    if fill_model == FILL_EXPLORATORY:
        notes.append("exploratory bar-close constant-bps fill; cannot qualify")

    for event in events:
        desired = signal(event, state)
        mark = event.price or event.bid or event.ask
        if mark is not None:
            state["last_mark"][event.symbol] = mark

        if event.event_type == "FUNDING" and event.funding_rate is not None:
            pos = state["position_perp"]
            last = state["last_mark"].get(event.symbol)
            if pos != 0 and last is not None:
                # Positive funding: longs pay shorts. Short perp (pos<0) receives.
                attr.funding += (-pos) * last * event.funding_rate

        if event.event_type not in {"MARK", "QUOTE", "FUNDING"} and desired == state["position_perp"]:
            continue
        if desired == state["position_perp"]:
            continue
        if mark is None:
            attr.partial_unfilled += Decimal("0")
            continue

        delta = desired - state["position_perp"]
        qty = cost_model.round_qty(delta * participation)
        if qty == 0:
            continue
        notional = (abs(qty) * mark)
        if notional < cost_model.min_notional:
            attr.partial_unfilled += notional
            continue

        attr.fees += cost_model.taker_fee(notional, perp=event.contract_kind == "PERPETUAL", adverse=adverse)
        attr.spread += cost_model.spread_cost(notional, adverse=adverse)
        attr.impact += cost_model.slippage_cost(notional)
        # Hedge: opposite spot of equal notional for basis/funding carry.
        hedge = -qty
        hedge_notional = abs(hedge) * mark
        attr.fees += cost_model.taker_fee(hedge_notional, perp=False, adverse=adverse)
        attr.spread += cost_model.spread_cost(hedge_notional, adverse=adverse)
        attr.impact += cost_model.slippage_cost(hedge_notional)

        state["position_perp"] += qty
        state["position_spot"] += hedge
        n_trades += 1

    artifact = CryptoEvidenceArtifact(
        hypothesis_id=hypothesis_id,
        fill_model=fill_model,
        can_qualify=can_qualify,
        partition=partition,
        cost_model_digest=_digest(cost_model.to_dict()),
        data_digest=data_digest,
        parameter_digest=_digest(parameters),
        attribution=attr,
        n_events=len(events),
        n_trades=n_trades,
        notes=notes,
        extra={"end_position_perp": str(state["position_perp"])},
    )
    return artifact
