"""Venue-aware crypto cost model. Research-only. No execution authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CryptoCostModel:
    venue_id: str
    spot_maker: Decimal
    spot_taker: Decimal
    perp_maker: Decimal
    perp_taker: Decimal
    assumed_spread_bps: Decimal
    slippage_bps: Decimal
    latency_ms: int
    min_notional: Decimal
    qty_precision: int
    price_precision: int
    adverse_spot_taker: Decimal
    adverse_perp_taker: Decimal
    adverse_spread_bps: Decimal
    label: str = "frozen_vip0_snapshot"

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key, value in list(out.items()):
            if isinstance(value, Decimal):
                out[key] = str(value)
        return out

    @staticmethod
    def binance_usdt_vip0() -> "CryptoCostModel":
        """Frozen 2026-08-14 snapshot. Not a live fee lookup."""
        return CryptoCostModel(
            venue_id="binance-vision",
            spot_maker=Decimal("0.001"),
            spot_taker=Decimal("0.001"),
            perp_maker=Decimal("0.0002"),
            perp_taker=Decimal("0.0005"),
            assumed_spread_bps=Decimal("1.0"),
            slippage_bps=Decimal("0.5"),
            latency_ms=250,
            min_notional=Decimal("5"),
            qty_precision=6,
            price_precision=2,
            adverse_spot_taker=Decimal("0.0015"),
            adverse_perp_taker=Decimal("0.0008"),
            adverse_spread_bps=Decimal("3.0"),
            label="binance_usdt_vip0_2026-08-14",
        )

    def round_qty(self, qty: Decimal) -> Decimal:
        q = qty.quantize(Decimal("1").scaleb(-self.qty_precision))
        return q

    def taker_fee(self, notional: Decimal, *, perp: bool, adverse: bool = False) -> Decimal:
        rate = (
            (self.adverse_perp_taker if adverse else self.perp_taker)
            if perp
            else (self.adverse_spot_taker if adverse else self.spot_taker)
        )
        return (abs(notional) * rate).copy_abs()

    def spread_cost(self, notional: Decimal, *, adverse: bool = False) -> Decimal:
        bps = self.adverse_spread_bps if adverse else self.assumed_spread_bps
        return (abs(notional) * bps / Decimal("10000")).copy_abs()

    def slippage_cost(self, notional: Decimal) -> Decimal:
        return (abs(notional) * self.slippage_bps / Decimal("10000")).copy_abs()
