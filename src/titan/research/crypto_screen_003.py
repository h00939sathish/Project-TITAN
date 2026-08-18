"""Preregistered CRYPTO-003: Order-Flow / Liquidity Imbalance Screen. Research-only.

Evaluates short-term order-flow imbalance (OFI) from sequence-valid trade records
net of taker fees, bid/ask spread, latency delay, and adverse impact.

The evidence pipeline (IS/OOS/adverse simulation, gates, bundle writing) lives in
``titan.research.crypto_screen.run_crypto_screen``; this module supplies the
signal function and the window-IC proxy for CRYPTO-003.
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


def order_flow_imbalance_signal(event: CryptoMarketEvent, state: dict[str, Any]) -> Decimal:
    """Computes volume-weighted Order Flow Imbalance (OFI) over rolling trades."""
    params = state.get("parameters", {})
    ofi_thresh = Decimal(str(params.get("ofi_threshold", "0.40")))
    window = int(params.get("rolling_window_trades", 100))

    if event.event_type != "TRADE" or event.qty is None or event.side is None:
        return Decimal("0")

    trades_hist: deque[tuple[Decimal, str]] = state.setdefault(
        "trades_history", deque(maxlen=window)
    )
    trades_hist.append((event.qty, event.side))

    if len(trades_hist) < window:
        return Decimal("0")

    buy_vol = sum((qty for qty, side in trades_hist if side == "BUY"), Decimal("0"))
    sell_vol = sum((qty for qty, side in trades_hist if side == "SELL"), Decimal("0"))
    total_vol = buy_vol + sell_vol

    if total_vol <= Decimal("0"):
        return Decimal("0")

    ofi = (buy_vol - sell_vol) / total_vol

    if ofi > ofi_thresh:
        return Decimal("1")  # Taker buy aggression -> LONG
    if ofi < -ofi_thresh:
        return Decimal("-1")  # Taker sell aggression -> SHORT

    return Decimal("0")


def _ofi_ic_proxy(oos_events: list[CryptoMarketEvent], prereg: PreRegistration) -> float:
    """Fraction of consecutive OOS event pairs where the position matched the next price move."""
    hits = 0
    total = 0
    sim_state: dict[str, Any] = {"parameters": prereg.parameters}
    for i in range(len(oos_events) - 1):
        ev = oos_events[i]
        next_ev = oos_events[i + 1]
        pos = order_flow_imbalance_signal(ev, sim_state)
        if pos != 0 and ev.price is not None and next_ev.price is not None:
            ret = (next_ev.price - ev.price) / ev.price
            total += 1
            if (pos * ret) > 0:
                hits += 1
    return (hits / total) if total else 0.0


def run_crypto_003(
    events: list[CryptoMarketEvent],
    manifest: CryptoDataManifest,
    prereg: PreRegistration,
    *,
    replicated: bool = False,
    allow_oos_for_parameters: bool = False,
) -> dict[str, Any]:
    """Run the CRYPTO-003 order-flow screen through the shared evidence pipeline."""
    return run_crypto_screen(
        order_flow_imbalance_signal,
        _ofi_ic_proxy,
        "CRYPTO-003",
        events,
        manifest,
        prereg,
        replicated=replicated,
        allow_oos_for_parameters=allow_oos_for_parameters,
    )


if __name__ == "__main__":
    raise SystemExit("import run_crypto_003 from tests or a driver; no CLI execution path")
