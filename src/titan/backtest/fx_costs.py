"""Immutable FX Cost Model for canonical research simulation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class FxCostModel:
    """Immutable cost model for FX simulations (ADR-031)."""

    venue: str
    account_currency: str
    quote_currency: str
    commission_bps: Decimal
    minimum_commission: Decimal
    half_spread_bps: Decimal
    slippage_bps: Decimal
    fill_mode: str
    swap_long_bps_day: Decimal = Decimal("0")
    swap_short_bps_day: Decimal = Decimal("0")
    version: str = "2.0"
    data_manifest_digest: str = ""

    def __post_init__(self) -> None:
        # commission_for_fill() treats notionals as USD; a non-USD account
        # currency would silently mislabel costs (ADR-031 fidelity).
        if self.account_currency != "USD":
            raise ValueError("account_currency must be USD")
        if self.commission_bps < Decimal("0"):
            raise ValueError("commission_bps cannot be negative")
        if self.minimum_commission < Decimal("0"):
            raise ValueError("minimum_commission cannot be negative")
        if self.half_spread_bps < Decimal("0"):
            raise ValueError("half_spread_bps cannot be negative")
        if self.slippage_bps < Decimal("0"):
            raise ValueError("slippage_bps cannot be negative")

    def commission_for_fill(self, notional_usd: Decimal) -> Decimal:
        """Calculate commission on a single fill in USD."""
        variable = abs(notional_usd) * self.commission_bps / Decimal("10000")
        return max(variable, self.minimum_commission)

    @classmethod
    def ibkr_spot_fx_tier_one(
        cls,
        fill_mode: str = "QUOTE_NEXT_EVENT",
        data_manifest_digest: str = "",
        quote_currency: str = "USD",
        swap_long_bps_day: Decimal = Decimal("-0.15"),
        swap_short_bps_day: Decimal = Decimal("-0.15"),
    ) -> FxCostModel:
        """Standard IBKR Spot FX Tier 1 schedule ($2.00 minimum, 0.20 bps)."""
        return cls(
            venue="IDEALPRO",
            account_currency="USD",
            quote_currency=quote_currency,
            commission_bps=Decimal("0.20"),
            minimum_commission=Decimal("2.00"),
            half_spread_bps=Decimal("0.10"),
            slippage_bps=Decimal("0.10"),
            fill_mode=fill_mode,
            swap_long_bps_day=swap_long_bps_day,
            swap_short_bps_day=swap_short_bps_day,
            version="2.0",
            data_manifest_digest=data_manifest_digest,
        )

    def with_adverse_costs(
        self,
        commission_bps: Decimal = Decimal("0.50"),
        half_spread_bps: Decimal = Decimal("0.50"),
        slippage_bps: Decimal = Decimal("0.50"),
        swap_long_bps_day: Decimal | None = None,
        swap_short_bps_day: Decimal | None = None,
    ) -> FxCostModel:
        """Create a copy with adverse/stressed cost parameters."""
        return FxCostModel(
            venue=self.venue,
            account_currency=self.account_currency,
            quote_currency=self.quote_currency,
            commission_bps=commission_bps,
            minimum_commission=self.minimum_commission,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
            fill_mode=self.fill_mode,
            swap_long_bps_day=swap_long_bps_day if swap_long_bps_day is not None else self.swap_long_bps_day,
            swap_short_bps_day=swap_short_bps_day if swap_short_bps_day is not None else self.swap_short_bps_day,
            version=self.version,
            data_manifest_digest=self.data_manifest_digest,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a canonical dictionary."""
        return {
            "version": self.version,
            "venue": self.venue,
            "account_currency": self.account_currency,
            "quote_currency": self.quote_currency,
            "commission_bps": str(self.commission_bps),
            "minimum_commission": str(self.minimum_commission),
            "half_spread_bps": str(self.half_spread_bps),
            "slippage_bps": str(self.slippage_bps),
            "fill_mode": self.fill_mode,
            "swap_long_bps_day": str(self.swap_long_bps_day),
            "swap_short_bps_day": str(self.swap_short_bps_day),
            "data_manifest_digest": self.data_manifest_digest,
        }

    def digest(self) -> str:
        """Compute deterministic SHA-256 hash of the canonical model configuration."""
        canonical_json = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def daily_swap_multiplier(self, weekday: int) -> int:
        """Calculate how many days of swap to apply.
        
        In spot FX (T+2 settlement), Wednesday trades settle on Friday. 
        Roll held into Thursday settles on Monday (3 days interest).
        `weekday` represents the day of the week (0=Monday, ..., 2=Wednesday, 6=Sunday).
        """
        # Wednesday (weekday == 2) pays triple swap due to weekend T+2 skip.
        if weekday == 2:
            return 3
        # Saturday/Sunday typically quote 0 swap because it's rolled on Wed.
        if weekday in (5, 6):
            return 0
        return 1
