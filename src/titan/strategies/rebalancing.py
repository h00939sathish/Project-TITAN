"""Portfolio Rebalancing & Weight Target Allocation Engine for TITAN."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from titan._core import Money, TradeIntent


@dataclass
class RebalanceConfig:
    rebalance_threshold_pct: float = 2.0  # Drift % threshold to trigger trade (e.g., 2%)
    min_trade_notional: float = 100.0     # Minimum trade size in USD
    cash_buffer_pct: float = 5.0          # Unallocated cash buffer %
    strategy_id: str = "portfolio_rebalancer"
    account_id: str = "paper-1"


@dataclass
class RebalanceIntent:
    instrument_id: str
    side: str                          # "BUY" or "SELL"
    quantity: int
    target_weight: float
    current_weight: float
    estimated_notional: float
    reason: str = ""


class RebalanceCalculator:
    """Calculates target portfolio positions and generates rebalancing trade intents."""

    def __init__(self, config: RebalanceConfig | None = None):
        self.config = config or RebalanceConfig()

    def compute_rebalance_intents(
        self,
        current_positions: dict[str, int],       # instrument_id -> quantity
        current_prices: dict[str, float],        # instrument_id -> price
        target_weights: dict[str, float],        # instrument_id -> target weight (0.0 to 1.0)
        cash_balance: float,                     # current cash in USD
    ) -> list[RebalanceIntent]:
        """Compute rebalance trade intents needed to match target_weights."""
        # 1. Compute total portfolio value
        positions_value = sum(
            qty * current_prices.get(instr, 0.0)
            for instr, qty in current_positions.items()
        )
        total_equity = cash_balance + positions_value

        if total_equity <= 0.0:
            return []

        # 2. Account for cash buffer
        allocatable_equity = total_equity * (1.0 - self.config.cash_buffer_pct / 100.0)

        intents: list[RebalanceIntent] = []
        all_instruments = set(current_positions.keys()) | set(target_weights.keys())

        for instr in sorted(all_instruments):
            price = current_prices.get(instr, 0.0)
            if price <= 0.0:
                continue

            current_qty = current_positions.get(instr, 0)
            current_val = current_qty * price
            current_weight = (current_val / total_equity) * 100.0 if total_equity > 0 else 0.0

            target_weight = target_weights.get(instr, 0.0) * 100.0  # Percentage
            weight_drift = abs(target_weight - current_weight)

            # Filter small weight drifts
            if weight_drift < self.config.rebalance_threshold_pct:
                continue

            target_val = allocatable_equity * (target_weight / 100.0)
            target_qty = int(target_val / price)

            qty_diff = target_qty - current_qty
            if qty_diff == 0:
                continue

            side = "BUY" if qty_diff > 0 else "SELL"
            abs_qty = abs(qty_diff)
            estimated_notional = abs_qty * price

            # Filter tiny trade notionals
            if estimated_notional < self.config.min_trade_notional:
                continue

            intents.append(
                RebalanceIntent(
                    instrument_id=instr,
                    side=side,
                    quantity=abs_qty,
                    target_weight=target_weight / 100.0,
                    current_weight=current_weight / 100.0,
                    estimated_notional=estimated_notional,
                    reason=f"Rebalance drift {weight_drift:.2f}% >= {self.config.rebalance_threshold_pct}%",
                )
            )

        return intents

    def to_trade_intents(
        self,
        rebalance_intents: list[RebalanceIntent],
        current_prices: dict[str, float],
        market_data_timestamp: str,
    ) -> list[TradeIntent]:
        """Convert RebalanceIntents into deterministic Rust TradeIntents for RiskGate evaluation."""
        result: list[TradeIntent] = []
        for ri in rebalance_intents:
            price = current_prices.get(ri.instrument_id, 0.0)
            result.append(
                TradeIntent(
                    strategy_id=self.config.strategy_id,
                    strategy_package_digest="",
                    account_id=self.config.account_id,
                    instrument_id=ri.instrument_id,
                    side=ri.side,
                    quantity=str(ri.quantity),
                    order_type="MARKET",
                    time_in_force="DAY",
                    risk_profile_version="1.0",
                    market_data_timestamp=market_data_timestamp,
                )
            )
        return result
