"""Deterministic fill models for research and backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from titan.backtest.fx_costs import FxCostModel


@dataclass
class FillResult:
    fill_price: float | Decimal
    fill_quantity: int | Decimal
    fill_cost: float | Decimal
    slippage: float | Decimal
    commission: float | Decimal
    spread_cost: float | Decimal = 0.0
    slippage_cost: float | Decimal = 0.0
    fidelity: str = "standard"


class BarConservativeFillModel:
    """Conservative fill model supporting bar execution and quote-sided canonical FX simulation."""

    def __init__(self, slippage_bps: float = 0.5, commission_bps: float = 1.0):
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps

    def fill(
        self,
        bar: dict[str, Any],
        side: str,
        quantity: int | Decimal,
        *,
        cost_model: FxCostModel | None = None,
    ) -> FillResult:
        side_norm = side.lower()
        if side_norm not in ("buy", "sell"):
            raise ValueError(f"Invalid trade side: '{side}'")

        if cost_model is not None:
            qty_dec = Decimal(str(quantity))
            if cost_model.fill_mode == "QUOTE_NEXT_EVENT":
                if side_norm == "buy":
                    if "ask" not in bar or bar["ask"] is None:
                        raise ValueError("Missing required quote field 'ask' for QUOTE_NEXT_EVENT buy fill")
                    base_price = Decimal(str(bar["ask"]))
                    slippage = base_price * cost_model.slippage_bps / Decimal("10000")
                    fill_price = base_price + slippage
                else:
                    if "bid" not in bar or bar["bid"] is None:
                        raise ValueError("Missing required quote field 'bid' for QUOTE_NEXT_EVENT sell fill")
                    base_price = Decimal(str(bar["bid"]))
                    slippage = base_price * cost_model.slippage_bps / Decimal("10000")
                    fill_price = base_price - slippage

                fill_cost = fill_price * qty_dec
                commission = cost_model.commission_for_fill(fill_cost)
                slippage_cost = slippage * qty_dec
                spread_cost = Decimal("0")
                fidelity = "quote"

            elif cost_model.fill_mode == "BAR_NEXT_OPEN":
                if "open" in bar and bar["open"] is not None:
                    base_price = Decimal(str(bar["open"]))
                elif "close" in bar and bar["close"] is not None:
                    base_price = Decimal(str(bar["close"]))
                else:
                    raise ValueError("Missing price data ('open' or 'close') for BAR_NEXT_OPEN fill")

                half_spread = base_price * cost_model.half_spread_bps / Decimal("10000")
                slippage = base_price * cost_model.slippage_bps / Decimal("10000")
                if side_norm == "buy":
                    fill_price = base_price + half_spread + slippage
                else:
                    fill_price = base_price - half_spread - slippage

                fill_cost = fill_price * qty_dec
                commission = cost_model.commission_for_fill(fill_cost)
                spread_cost = half_spread * qty_dec
                slippage_cost = slippage * qty_dec
                fidelity = "lower"
            else:
                raise ValueError(f"Unsupported fill_mode: {cost_model.fill_mode}")

            return FillResult(
                fill_price=fill_price,
                fill_quantity=int(qty_dec) if qty_dec == int(qty_dec) else qty_dec,
                fill_cost=fill_cost,
                slippage=slippage,
                commission=commission,
                spread_cost=spread_cost,
                slippage_cost=slippage_cost,
                fidelity=fidelity,
            )

        # Legacy / default non-cost_model behavior (e.g. standard equity tests)
        close = float(bar.get("close", bar.get("open", 0.0)))
        slippage = close * self.slippage_bps / 10000.0
        fill_price = close + slippage if side_norm == "buy" else close - slippage
        fill_cost = fill_price * float(quantity)
        commission = fill_cost * self.commission_bps / 10000.0
        return FillResult(
            fill_price=round(fill_price, 2),
            fill_quantity=int(quantity),
            fill_cost=round(fill_cost, 2),
            slippage=round(slippage, 2),
            commission=round(commission, 2),
            fidelity="standard",
        )
