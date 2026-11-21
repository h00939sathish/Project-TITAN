"""Sleeve C: Defined-Risk Systematic Options Engine for Project TITAN Tournament.

Constructs quantitative defined-risk credit spreads (Bull Put Spreads / Iron Condors) on SPY/QQQ
targeting 15-20 Delta with explicit $0.65/contract fee attribution and max-loss capping.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional


DEFAULT_OPTIONS_CAPITAL = 15000.0
ALPACA_OPTION_CONTRACT_FEE = 0.65


@dataclass(frozen=True)
class OptionSpreadIntent:
    underlying: str
    strategy_type: str        # "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR"
    short_strike: float
    long_strike: float
    expiration_date: str
    target_credit_usd: float
    max_loss_usd: float
    contracts: int
    contract_fees_usd: float
    short_contract_symbol: str
    long_contract_symbol: str


class OptionsSleeveEngine:
    """Manages defined-risk systematic option spreads on SPY / QQQ."""

    def __init__(
        self,
        allocated_capital_usd: float = DEFAULT_OPTIONS_CAPITAL,
        max_collateral_per_trade: float = 750.0, # 5% max risk per spread
        target_delta: float = 0.18,              # ~82% probability of profit
        min_dte: int = 14,
        max_dte: int = 35,
    ):
        self.allocated_capital_usd = allocated_capital_usd
        self.max_collateral_per_trade = max_collateral_per_trade
        self.target_delta = target_delta
        self.min_dte = min_dte
        self.max_dte = max_dte

    def construct_bull_put_spread(
        self,
        underlying_price: float,
        underlying_symbol: str = "SPY",
        spread_width: float = 5.0, # $5 wide spread
        expiration_date: str = "2026-12-18",
    ) -> OptionSpreadIntent:
        """Constructs a systematic bull put credit spread below current market price."""
        # 18 Delta strike approximation (~3-4% OTM)
        short_strike = round(underlying_price * (1.0 - 0.035), 0)
        long_strike = short_strike - spread_width

        # Conservative credit assumption (~20% of width = $1.00 credit on $5 width)
        est_credit_per_share = 0.85
        total_credit_per_contract = est_credit_per_share * 100.0
        max_loss_per_contract = (spread_width - est_credit_per_share) * 100.0

        # Number of contracts capped by max_collateral_per_trade
        contracts = max(1, int(self.max_collateral_per_trade / max_loss_per_contract))
        total_max_loss = max_loss_per_contract * contracts
        total_credit = total_credit_per_contract * contracts
        fees = ALPACA_OPTION_CONTRACT_FEE * 2 * contracts # 2 legs per contract

        return OptionSpreadIntent(
            underlying=underlying_symbol,
            strategy_type="BULL_PUT_SPREAD",
            short_strike=short_strike,
            long_strike=long_strike,
            expiration_date=expiration_date,
            target_credit_usd=round(total_credit, 2),
            max_loss_usd=round(total_max_loss, 2),
            contracts=contracts,
            contract_fees_usd=round(fees, 2),
            short_contract_symbol=f"{underlying_symbol}_{expiration_date}_P{int(short_strike)}",
            long_contract_symbol=f"{underlying_symbol}_{expiration_date}_P{int(long_strike)}",
        )

    def evaluate_sleeve(
        self,
        current_prices: Mapping[str, float],
        current_options_positions: Mapping[str, Any],
        total_account_equity: float,
    ) -> Dict[str, Any]:
        """Evaluates option opportunities and collateral utilization."""
        sleeve_budget = min(self.allocated_capital_usd, total_account_equity * 0.20)
        spy_price = current_prices.get("SPY", 580.0)

        # Generate candidates
        spread = self.construct_bull_put_spread(
            underlying_price=spy_price,
            underlying_symbol="SPY",
            spread_width=5.0,
            expiration_date="2026-12-18",
        )

        return {
            "sleeve_name": "options_defined_risk",
            "sleeve_budget_usd": sleeve_budget,
            "underlying_price": spy_price,
            "active_positions_count": len(current_options_positions),
            "candidate_spread": spread,
        }
