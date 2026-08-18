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
    version: str = "1.0"
    data_manifest_digest: str = ""

    def __post_init__(self) -> None:
        if self.account_currency != "USD":
            raise ValueError(
                f"Unsupported account_currency '{self.account_currency}'. "
                "v1 FX cost model strictly supports USD-account only."
            )
        if self.quote_currency != "USD":
            raise ValueError(
                f"Unsupported quote_currency '{self.quote_currency}'. "
                "v1 FX cost model strictly supports USD-quoted FX instruments only."
            )
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
    ) -> FxCostModel:
        """Standard IBKR Spot FX Tier 1 schedule ($2.00 minimum, 0.20 bps)."""
        return cls(
            venue="IDEALPRO",
            account_currency="USD",
            quote_currency="USD",
            commission_bps=Decimal("0.20"),
            minimum_commission=Decimal("2.00"),
            half_spread_bps=Decimal("0.10"),
            slippage_bps=Decimal("0.10"),
            fill_mode=fill_mode,
            version="1.0",
            data_manifest_digest=data_manifest_digest,
        )

    def with_adverse_costs(
        self,
        commission_bps: Decimal = Decimal("0.50"),
        half_spread_bps: Decimal = Decimal("0.50"),
        slippage_bps: Decimal = Decimal("0.50"),
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
            "data_manifest_digest": self.data_manifest_digest,
        }

    def digest(self) -> str:
        """Compute deterministic SHA-256 hash of the canonical model configuration."""
        canonical_json = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
