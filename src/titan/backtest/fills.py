"""Bar-conservative fill model. Fills at the close price within the bar."""

from dataclasses import dataclass


@dataclass
class FillResult:
    fill_price: float
    fill_quantity: int
    fill_cost: float
    slippage: float
    commission: float


class BarConservativeFillModel:
    def __init__(self, slippage_bps: float = 0.5, commission_bps: float = 1.0):
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps

    def fill(self, bar: dict, side: str, quantity: int) -> FillResult:
        close = bar["close"]
        slippage = close * self.slippage_bps / 10000
        fill_price = close + slippage if side == "buy" else close - slippage
        fill_cost = fill_price * quantity
        commission = fill_cost * self.commission_bps / 10000
        return FillResult(
            fill_price=round(fill_price, 2),
            fill_quantity=quantity,
            fill_cost=round(fill_cost, 2),
            slippage=round(slippage, 2),
            commission=round(commission, 2),
        )
