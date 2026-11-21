"""Alpaca Regulatory & Surveillance Compliance Gate for Project TITAN.

Enforces FINRA Rule 4210 (PDT capital rules), holding period minimums,
Alpaca non-retail surveillance boundaries (fill-to-cancel ratios), and
Easy-to-Borrow ($0 borrow fee) short constraints.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional


class AlpacaAccountTier(str, Enum):
    """Account operational tier based on capital safety boundaries."""
    RESTRICTED = "RESTRICTED"      # Equity < $26,250 (Danger of PDT cliff: freeze new entries)
    LONG_ONLY_HEDGED = "LONG_ONLY_HEDGED"  # $26,250 <= Equity < $30,000 (Council amendment: Long-only + Index hedge)
    FULL_LONG_SHORT = "FULL_LONG_SHORT"    # Equity >= $30,000 (Permits pure dollar-neutral L/S factor baskets)


@dataclass
class AlpacaComplianceConfig:
    """Configurable thresholds for Alpaca compliance gate."""
    # FINRA PDT Boundaries
    pdt_capital_floor: Decimal = Decimal("25000.00")
    pdt_buffer_equity: Decimal = Decimal("26250.00")        # 5% safety buffer
    long_short_equity_threshold: Decimal = Decimal("30000.00")  # Council amendment
    
    # Holding Period Rules
    min_holding_seconds: float = 24.0 * 3600.0              # Mandatory overnight holding (zero day-trades)
    
    # Alpaca Surveillance Defenses (Non-Retail Avoidance)
    min_fill_to_cancel_ratio: float = 0.70                  # Must maintain >= 70% fill ratio
    ban_auction_cross_orders: bool = True                   # Avoid MOO/MOC targeting
    max_notional_per_order: Decimal = Decimal("50000.00")   # Prevent suspicious jumbo orders
    min_shares_per_order: int = 1                           # Reject zero-share anomalies
    
    # Short Locate & Borrow
    etb_only_shorts: bool = True                            # Require Easy-to-Borrow ($0 borrow fee)
    fail_closed_on_locate_error: bool = True                # Reject short if locate query fails


@dataclass
class SurveillanceMetrics:
    """Tracks order execution counts to prevent non-retail surveillance flags."""
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0

    @property
    def fill_to_cancel_ratio(self) -> float:
        total_resolved = self.orders_filled + self.orders_cancelled
        if total_resolved == 0:
            return 1.0
        return self.orders_filled / total_resolved


class AlpacaComplianceGate:
    """Gatekeeper ensuring automated trades adhere strictly to Alpaca retail policies."""

    def __init__(
        self,
        config: Optional[AlpacaComplianceConfig] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.config = config or AlpacaComplianceConfig()
        self._clock = clock
        self.metrics = SurveillanceMetrics()

    def get_account_tier(self, current_equity: Decimal) -> AlpacaAccountTier:
        """Evaluate account tier against FINRA Rule 4210 and Council thresholds."""
        if current_equity < self.config.pdt_buffer_equity:
            return AlpacaAccountTier.RESTRICTED
        if current_equity < self.config.long_short_equity_threshold:
            return AlpacaAccountTier.LONG_ONLY_HEDGED
        return AlpacaAccountTier.FULL_LONG_SHORT

    def validate_entry(
        self,
        symbol: str,
        side: str,
        shares: int,
        notional_usd: Decimal,
        current_equity: Decimal,
        is_etb: Optional[bool] = None,
        order_type: str = "limit",
        time_in_force: str = "day",
    ) -> tuple[bool, str]:
        """Validate proposed entry order against capital, surveillance, and short borrow rules."""
        side_lower = side.lower()
        tier = self.get_account_tier(current_equity)

        # 1. Capital & PDT Buffer Check
        if tier == AlpacaAccountTier.RESTRICTED:
            return False, (
                f"REJECTED: Account equity (${current_equity:.2f}) is within 5% buffer of the "
                f"PDT threshold (${self.config.pdt_capital_floor:.2f}). New entries frozen."
            )

        # 2. Auction Cross Ban Check (Alpaca Non-Retail Surveillance rule)
        if self.config.ban_auction_cross_orders:
            tif_lower = time_in_force.lower()
            if tif_lower in ("opg", "cls") or "moo" in order_type.lower() or "moc" in order_type.lower():
                return False, "REJECTED: Market-on-Open/Close cross auction orders are prohibited."

        # 3. Micro/Jumbo Order Checks
        if shares < self.config.min_shares_per_order:
            return False, f"REJECTED: Order share count ({shares}) is below minimum allowed."
        if notional_usd > self.config.max_notional_per_order:
            return False, (
                f"REJECTED: Order notional (${notional_usd:.2f}) exceeds retail safety limit "
                f"(${self.config.max_notional_per_order:.2f})."
            )

        # 4. Short Borrow & ETB Validation
        if side_lower in ("short", "sell_short"):
            if tier == AlpacaAccountTier.LONG_ONLY_HEDGED:
                return False, (
                    f"REJECTED: Account equity (${current_equity:.2f}) is below Long/Short threshold "
                    f"(${self.config.long_short_equity_threshold:.2f}). Only Long-Only + Index hedge permitted."
                )

            if self.config.etb_only_shorts:
                if is_etb is None and self.config.fail_closed_on_locate_error:
                    return False, f"REJECTED: Locate status unknown for {symbol}. Fail-closed on short intent."
                if is_etb is False:
                    return False, (
                        f"REJECTED: {symbol} is Hard-To-Borrow (HTB). Only Easy-To-Borrow (ETB) "
                        f"shorts with $0 borrow cost are authorized."
                    )

        # 5. Surveillance Fill Ratio Warning Check
        if self.metrics.orders_submitted >= 10:
            if self.metrics.fill_to_cancel_ratio < self.config.min_fill_to_cancel_ratio:
                return False, (
                    f"REJECTED: Fill-to-cancel ratio ({self.metrics.fill_to_cancel_ratio:.1%}) is below "
                    f"Alpaca surveillance floor ({self.config.min_fill_to_cancel_ratio:.1%}). Throttling entries."
                )

        self.metrics.orders_submitted += 1
        return True, "AUTHORIZED"

    def validate_exit(
        self,
        symbol: str,
        entry_timestamp: float,
        is_emergency_killswitch: bool = False,
    ) -> tuple[bool, str]:
        """Validate position exit against holding period minimums to prevent day trading."""
        if is_emergency_killswitch:
            return True, "AUTHORIZED: Emergency kill-switch override."

        elapsed_seconds = self._clock() - entry_timestamp
        if elapsed_seconds < self.config.min_holding_seconds:
            remaining_hours = (self.config.min_holding_seconds - elapsed_seconds) / 3600.0
            return False, (
                f"REJECTED: Minimum holding period not satisfied for {symbol}. "
                f"Elapsed: {elapsed_seconds / 3600.0:.1f}h, Required: {self.config.min_holding_seconds / 3600.0:.1f}h "
                f"({remaining_hours:.1f}h remaining). Day trade blocked under FINRA PDT rules."
            )

        return True, "AUTHORIZED"

    def record_fill(self) -> None:
        """Record successful broker fill."""
        self.metrics.orders_filled += 1

    def record_cancellation(self) -> None:
        """Record order cancellation."""
        self.metrics.orders_cancelled += 1
