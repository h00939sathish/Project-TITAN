"""Alpaca Paced Batch Dispatcher & Rebalance Scheduler for Project TITAN.

Coordinates multi-asset factor portfolio rebalances while strictly adhering to:
- Alpaca REST rate limits (100ms pacing)
- AlpacaComplianceGate validation (PDT buffer, ETB shorts, holding periods)
- Council capital tiers ($30k L/S threshold)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from titan.risk.alpaca_compliance import (
    AlpacaAccountTier,
    AlpacaComplianceGate,
)


@dataclass
class BatchOrderIntent:
    """Represents a validated order intent to be dispatched to Alpaca."""
    symbol: str
    side: str  # "buy", "sell", "short", "buy_to_cover"
    shares: int
    target_price: Decimal
    notional_usd: Decimal
    is_etb: bool = True
    order_type: str = "limit"
    time_in_force: str = "day"


@dataclass
class BatchExecutionReceipt:
    """Summary of a completed rebalance batch dispatch."""
    timestamp: float
    account_tier: str
    starting_equity: Decimal
    orders_authorized: int
    orders_rejected: int
    orders_dispatched: int
    rejections: List[Tuple[str, str]] = field(default_factory=list)
    dispatched_orders: List[Dict[str, Any]] = field(default_factory=list)
    total_rebalanced_notional: Decimal = Decimal("0.00")


class AlpacaBatchDispatcher:
    """Paced batch order execution engine for Alpaca API."""

    def __init__(
        self,
        compliance_gate: AlpacaComplianceGate,
        broker_client: Any = None,
        pacing_delay_seconds: float = 0.10,  # 100ms delay between API calls (consumes <10% rate quota)
        clock: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.compliance_gate = compliance_gate
        self.broker_client = broker_client
        self.pacing_delay = pacing_delay_seconds
        self._clock = clock
        self._sleep = sleep_fn

    def compute_target_deltas(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        total_equity: Decimal,
        current_positions: Dict[str, int],  # symbol -> shares currently held
        etb_status: Optional[Dict[str, bool]] = None,
    ) -> List[BatchOrderIntent]:
        """Compute delta share orders required to transition current portfolio to target weights."""
        intents: List[BatchOrderIntent] = []
        etb_map = etb_status or {}

        # Merge symbols from both target weights and current positions
        all_symbols = sorted(set(target_weights.keys()).union(current_positions.keys()))

        for symbol in all_symbols:
            price = Decimal(str(current_prices.get(symbol, 0.0)))
            if price <= Decimal("0"):
                continue

            current_shares = current_positions.get(symbol, 0)
            target_weight = target_weights.get(symbol, 0.0)
            
            # Dollar target for this symbol
            target_notional = total_equity * Decimal(str(target_weight))
            target_shares = int(target_notional / price)

            delta_shares = target_shares - current_shares
            if delta_shares == 0:
                continue

            is_etb = etb_map.get(symbol, True)
            abs_shares = abs(delta_shares)
            order_notional = (Decimal(abs_shares) * price).quantize(Decimal("0.01"))

            # Determine execution side
            if delta_shares > 0:
                side = "buy" if current_shares >= 0 else "buy_to_cover"
            else:
                side = "sell" if current_shares > 0 else "short"

            intents.append(
                BatchOrderIntent(
                    symbol=symbol,
                    side=side,
                    shares=abs_shares,
                    target_price=price,
                    notional_usd=order_notional,
                    is_etb=is_etb,
                )
            )

        return intents

    def execute_rebalance(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        total_equity: Decimal,
        current_positions: Dict[str, int],
        etb_status: Optional[Dict[str, bool]] = None,
    ) -> BatchExecutionReceipt:
        """Validate and dispatch a complete rebalance batch with rate pacing."""
        now = self._clock()
        tier = self.compliance_gate.get_account_tier(total_equity)

        receipt = BatchExecutionReceipt(
            timestamp=now,
            account_tier=tier.value,
            starting_equity=total_equity,
            orders_authorized=0,
            orders_rejected=0,
            orders_dispatched=0,
        )

        # Fail fast if account is restricted
        if tier == AlpacaAccountTier.RESTRICTED:
            receipt.rejections.append(("PORTFOLIO", f"Account restricted due to capital buffer (${total_equity:.2f})"))
            return receipt

        # Compute required orders
        intents = self.compute_target_deltas(
            target_weights=target_weights,
            current_prices=current_prices,
            total_equity=total_equity,
            current_positions=current_positions,
            etb_status=etb_status,
        )

        # Process each intent through compliance gate and dispatch with pacing
        for intent in intents:
            ok, reason = self.compliance_gate.validate_entry(
                symbol=intent.symbol,
                side=intent.side,
                shares=intent.shares,
                notional_usd=intent.notional_usd,
                current_equity=total_equity,
                is_etb=intent.is_etb,
                order_type=intent.order_type,
                time_in_force=intent.time_in_force,
            )

            if not ok:
                receipt.orders_rejected += 1
                receipt.rejections.append((intent.symbol, reason))
                continue

            receipt.orders_authorized += 1

            # Dispatch order to broker if client exists
            order_record: Dict[str, Any] = {
                "symbol": intent.symbol,
                "side": intent.side,
                "shares": intent.shares,
                "price": float(intent.target_price),
                "notional": float(intent.notional_usd),
            }

            if self.broker_client is not None and hasattr(self.broker_client, "place_order"):
                try:
                    # Broker dispatch
                    self.broker_client.place_order(intent)
                    self.compliance_gate.record_fill()
                except Exception as exc:
                    self.compliance_gate.record_cancellation()
                    receipt.rejections.append((intent.symbol, f"Broker API Exception: {exc}"))
                    continue
            else:
                # Simulated dispatch in test / dry-run mode
                self.compliance_gate.record_fill()

            receipt.orders_dispatched += 1
            receipt.total_rebalanced_notional += intent.notional_usd
            receipt.dispatched_orders.append(order_record)

            # Pacing delay to guarantee zero 429 rate limit errors
            if self.pacing_delay > 0:
                self._sleep(self.pacing_delay)

        return receipt
