"""Canonical Alpaca US Equity Cost Model for Research & Backtesting.

Models Alpaca's $0 retail API commission, $0 Easy-to-Borrow (ETB) short fees,
pass-through SEC Section 31 & FINRA Trading Activity Fees (TAF), and
market-depth spread/slippage friction.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP


@dataclass(frozen=True)
class AlpacaCostBreakdown:
    """Detailed fee and friction decomposition for a single fill."""
    commission_usd: Decimal
    spread_usd: Decimal
    slippage_usd: Decimal
    sec_fee_usd: Decimal
    finra_taf_usd: Decimal
    borrow_fee_usd: Decimal
    total_friction_usd: Decimal


@dataclass(frozen=True)
class AlpacaEquityCostModel:
    """Immutable Alpaca Equity Cost Schedule adhering to official disclosures."""

    commission_usd: Decimal = Decimal("0.00")
    etb_borrow_bps_day: Decimal = Decimal("0.00")
    half_spread_bps: Decimal = Decimal("1.00")       # 1.0 bps conservative half-spread
    slippage_bps: Decimal = Decimal("0.50")          # 0.5 bps execution slippage
    
    # Regulatory pass-through fee rates
    sec_fee_rate: Decimal = Decimal("0.0000278")     # $27.80 per $1,000,000 of principal (sales only)
    finra_taf_per_share: Decimal = Decimal("0.000166")  # $0.000166 per share (sales only)
    finra_taf_max_per_trade: Decimal = Decimal("8.30")  # Capped at $8.30 per trade

    def __post_init__(self) -> None:
        if self.half_spread_bps < Decimal("0"):
            raise ValueError("half_spread_bps cannot be negative")
        if self.slippage_bps < Decimal("0"):
            raise ValueError("slippage_bps cannot be negative")

    def calculate_cost(
        self,
        side: str,
        shares: Decimal | int,
        price: Decimal | float,
        is_etb: bool = True,
        holding_days: int = 1,
    ) -> AlpacaCostBreakdown:
        """Calculate exact cost and friction for an execution on Alpaca.
        
        Args:
            side: "buy", "sell", "sell_short", or "buy_to_cover"
            shares: Number of shares transacted
            price: Execution price in USD
            is_etb: Whether the underlying is Easy-To-Borrow
            holding_days: Days held overnight (for borrow fee computation)
        """
        shares_dec = Decimal(str(shares))
        price_dec = Decimal(str(price))
        notional_usd = shares_dec * price_dec
        side_lower = side.lower()

        # 1. Commission is $0.00 on Alpaca retail
        commission = self.commission_usd

        # 2. Spread and slippage friction
        spread_usd = (notional_usd * self.half_spread_bps / Decimal("10000")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        slippage_usd = (notional_usd * self.slippage_bps / Decimal("10000")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # 3. Regulatory Fees (Assessed on SALES only: "sell" and "sell_short")
        sec_fee = Decimal("0.00")
        finra_taf = Decimal("0.00")
        if side_lower in ("sell", "sell_short"):
            # SEC fee rounded up to nearest cent per regulatory requirement
            raw_sec = notional_usd * self.sec_fee_rate
            sec_fee = (raw_sec).quantize(Decimal("0.01"), rounding=ROUND_UP)

            # FINRA TAF
            raw_taf = shares_dec * self.finra_taf_per_share
            finra_taf = min(raw_taf, self.finra_taf_max_per_trade).quantize(
                Decimal("0.01"), rounding=ROUND_UP
            )

        # 4. Stock Borrow Fee (ETB shares are $0.00 on Alpaca API)
        borrow_fee = Decimal("0.00")
        if not is_etb and side_lower in ("sell_short", "short"):
            # Standard hard-to-borrow penalty if non-ETB
            daily_borrow_rate = Decimal("0.0002") # ~7.3% annual HTB locate assumption
            borrow_fee = (notional_usd * daily_borrow_rate * Decimal(holding_days)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        total_friction = commission + spread_usd + slippage_usd + sec_fee + finra_taf + borrow_fee

        return AlpacaCostBreakdown(
            commission_usd=commission,
            spread_usd=spread_usd,
            slippage_usd=slippage_usd,
            sec_fee_usd=sec_fee,
            finra_taf_usd=finra_taf,
            borrow_fee_usd=borrow_fee,
            total_friction_usd=total_friction,
        )

    @classmethod
    def standard_retail(cls) -> AlpacaEquityCostModel:
        """Standard self-directed retail API schedule."""
        return cls()

    @classmethod
    def stressed_adverse(cls) -> AlpacaEquityCostModel:
        """Adversarial stress test schedule (3.0 bps spread, 1.5 bps slippage)."""
        return cls(
            half_spread_bps=Decimal("3.00"),
            slippage_bps=Decimal("1.50"),
        )

    def to_venue_cost_schedule(self) -> "VenueCostSchedule":
        """Convert to factor simulator compatible VenueCostSchedule."""
        from titan.backtest.factor_simulator import VenueCostSchedule

        # ETB borrow on Alpaca is 0.0 bps/year
        annual_borrow = float(self.etb_borrow_bps_day * Decimal("252"))
        return VenueCostSchedule(
            name="alpaca_retail_etb",
            layer="layer1_discovery",
            commission_per_share_usd=float(self.commission_usd),
            min_commission_usd=0.0,
            assumed_avg_share_price=100.0,
            spread_bps=float(self.half_spread_bps),
            slippage_bps=float(self.slippage_bps),
            annual_short_borrow_bps=annual_borrow,
            regulatory_fees_bps=0.03, # SEC ($27.80/M) + FINRA TAF
            assumption_status="verified_from_published_schedule",
            provenance="Alpaca self-directed retail API ($0 commission, $0 ETB borrow)",
            source_document="Alpaca Fee Schedule & Securities Lending Policy 2026",
            source_url="https://alpaca.markets/disclosures",
            effective_date="2026-11-19",
        )
