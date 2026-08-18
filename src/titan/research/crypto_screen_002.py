"""Preregistered CRYPTO-002: Funding + Open-Interest Deleveraging Screen. Research-only.

Evaluates whether extreme funding rates combined with significant Open Interest
surges/collapses predict mean-reverting reversals net of trading friction and
adverse stress scenarios.

The evidence pipeline (IS/OOS/adverse simulation, gates, bundle writing) lives in
``titan.research.crypto_screen.run_crypto_screen``; this module supplies the
signal function and the window-IC proxy for CRYPTO-002.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Any

from titan.data.crypto import CryptoDataManifest, CryptoMarketEvent
from titan.research.crypto_screen import (
    PreRegistration,
    run_crypto_screen,
)


def funding_oi_deleveraging_signal(event: CryptoMarketEvent, state: dict[str, Any]) -> Decimal:
    """Predicts post-event reversal from extreme funding and OI buildup/flush.

    - Extreme positive funding + OI expansion: speculative long crowding -> SHORT (-1)
    - Extreme positive funding + OI collapse: long flush/liquidation exhaust -> BUY (1)
    - Extreme negative funding + OI expansion: speculative short crowding -> BUY (1)
    - Extreme negative funding + OI collapse: short squeeze exhaust -> SHORT (-1)
    """
    params = state.get("parameters", {})
    funding_thresh = Decimal(str(params.get("funding_abs_threshold", "0.0003")))
    oi_thresh = Decimal(str(params.get("oi_change_threshold_pct", "0.03")))
    lookback = int(params.get("oi_lookback_intervals", 24))

    # Update state from incoming event
    if event.event_type == "FUNDING" and event.funding_rate is not None:
        state["last_funding"] = event.funding_rate

    if event.event_type == "OPEN_INTEREST" and event.open_interest is not None:
        oi_hist: deque[Decimal] = state.setdefault("oi_history", deque(maxlen=lookback))
        oi_hist.append(event.open_interest)
        if len(oi_hist) >= lookback and oi_hist[0] > 0:
            first_oi = oi_hist[0]
            curr_oi = oi_hist[-1]
            state["oi_change_pct"] = (curr_oi - first_oi) / first_oi

    last_funding: Decimal | None = state.get("last_funding")
    oi_change_pct: Decimal | None = state.get("oi_change_pct")

    if last_funding is None or oi_change_pct is None:
        return Decimal("0")

    # High positive funding (longs paying shorts)
    if last_funding > funding_thresh:
        if oi_change_pct > oi_thresh:
            return Decimal("-1")  # Crowded long buildup -> fade
        if oi_change_pct < -oi_thresh:
            return Decimal("1")  # Liquidation flush complete -> mean revert

    # High negative funding (shorts paying longs)
    if last_funding < -funding_thresh:
        if oi_change_pct > oi_thresh:
            return Decimal("1")  # Crowded short buildup -> squeeze long
        if oi_change_pct < -oi_thresh:
            return Decimal("-1")  # Short squeeze flush complete -> mean revert

    return Decimal("0")


def _oi_ic_proxy(oos_events: list[CryptoMarketEvent], prereg: PreRegistration) -> float:
    """Fraction of OOS funding events where the position profited from the funding sign."""
    hits = 0
    total = 0
    sim_state: dict[str, Any] = {"parameters": prereg.parameters}
    for ev in oos_events:
        pos = funding_oi_deleveraging_signal(ev, sim_state)
        if pos != 0 and ev.event_type == "FUNDING" and ev.funding_rate is not None:
            total += 1
            # Check if position profited from funding sign direction
            if (pos * ev.funding_rate) < 0:
                hits += 1
    return (hits / total) if total else 0.0


def run_crypto_002(
    events: list[CryptoMarketEvent],
    manifest: CryptoDataManifest,
    prereg: PreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Run the CRYPTO-002 funding+OI screen through the shared evidence pipeline."""
    return run_crypto_screen(
        funding_oi_deleveraging_signal,
        _oi_ic_proxy,
        "CRYPTO-002",
        events,
        manifest,
        prereg,
        replicated=replicated,
        allow_oos_for_parameters=allow_oos_for_parameters,
    )


if __name__ == "__main__":
    raise SystemExit("import run_crypto_002 from tests or a driver; no CLI execution path")
