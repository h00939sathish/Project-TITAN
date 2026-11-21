"""TITAN Multi-Asset Tournament Manager.

Orchestrates 3 parallel sleeves across Alpaca's paper trading environment:
1. Sleeve A ($60k / 60%): Equity Factor Swing (PEAD + Quality L/S)
2. Sleeve B ($25k / 25%): 24/7 Crypto Trend Following (BTC/ETH/SOL)
3. Sleeve C ($15k / 15%): Defined-Risk Options Systematic Spreads (SPY/QQQ)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from titan.tournament.crypto_sleeve import CryptoSleeveEngine, DEFAULT_CRYPTO_CAPITAL
from titan.tournament.options_sleeve import OptionsSleeveEngine, DEFAULT_OPTIONS_CAPITAL


@dataclass
class SleeveTelemetry:
    name: str
    target_capital_usd: float
    current_value_usd: float
    unrealized_pnl_usd: float
    cumulative_fees_usd: float
    active_orders_count: int
    open_positions_count: int
    status: str = "ACTIVE"


class TournamentManager:
    """Central coordination hub for the 3-sleeve multi-asset paper competition."""

    def __init__(
        self,
        total_account_capital: float = 100000.0,
        equity_budget: float = 60000.0,
        crypto_budget: float = DEFAULT_CRYPTO_CAPITAL,
        options_budget: float = DEFAULT_OPTIONS_CAPITAL,
    ):
        self.total_account_capital = total_account_capital
        self.equity_budget = equity_budget
        self.crypto_engine = CryptoSleeveEngine(allocated_capital_usd=crypto_budget)
        self.options_engine = OptionsSleeveEngine(allocated_capital_usd=options_budget)

    def evaluate_tournament(
        self,
        account_equity: float,
        equity_summary: Optional[Dict[str, Any]] = None,
        crypto_prices: Optional[Mapping[str, pd.Series]] = None,
        crypto_positions: Optional[Mapping[str, float]] = None,
        options_positions: Optional[Mapping[str, Any]] = None,
        current_market_prices: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, Any]:
        """Runs evaluation across all 3 sleeves and generates the unified scoreboard."""
        now_utc = datetime.now(timezone.utc).isoformat()
        prices = current_market_prices or {}

        # 1. Sleeve A: Equities
        eq_telemetry = SleeveTelemetry(
            name="Sleeve A: US Equities (PEAD + Quality L/S)",
            target_capital_usd=self.equity_budget,
            current_value_usd=float(equity_summary.get("total_equity", self.equity_budget)) if equity_summary else self.equity_budget,
            unrealized_pnl_usd=float(equity_summary.get("unrealized_pnl", 0.0)) if equity_summary else 0.0,
            cumulative_fees_usd=float(equity_summary.get("total_fees", 0.0)) if equity_summary else 0.0,
            active_orders_count=int(equity_summary.get("orders_count", 0)) if equity_summary else 0,
            open_positions_count=int(equity_summary.get("positions_count", 0)) if equity_summary else 0,
            status="ACTIVE (10:30 AM ET Rebalance)",
        )

        # 2. Sleeve B: 24/7 Crypto
        crypto_res = None
        if crypto_prices:
            crypto_res = self.crypto_engine.evaluate_sleeve(
                prices_map=crypto_prices,
                current_positions=crypto_positions or {},
                total_account_equity=account_equity,
            )

        crypto_orders = crypto_res.get("delta_orders", []) if crypto_res else []
        crypto_fees = sum(o.get("estimated_fee_usd", 0.0) for o in crypto_orders)

        crypto_telemetry = SleeveTelemetry(
            name="Sleeve B: 24/7 Crypto Trend (BTC/ETH/SOL)",
            target_capital_usd=self.crypto_engine.allocated_capital_usd,
            current_value_usd=self.crypto_engine.allocated_capital_usd,
            unrealized_pnl_usd=0.0,
            cumulative_fees_usd=crypto_fees,
            active_orders_count=len(crypto_orders),
            open_positions_count=len(crypto_positions or {}),
            status="ACTIVE (Continuous 24/7)",
        )

        # 3. Sleeve C: Defined-Risk Options
        options_res = self.options_engine.evaluate_sleeve(
            current_prices=prices,
            current_options_positions=options_positions or {},
            total_account_equity=account_equity,
        )
        opt_spread = options_res.get("candidate_spread")
        opt_fees = opt_spread.contract_fees_usd if opt_spread else 0.0

        options_telemetry = SleeveTelemetry(
            name="Sleeve C: Defined-Risk Options (SPY Spreads)",
            target_capital_usd=self.options_engine.allocated_capital_usd,
            current_value_usd=self.options_engine.allocated_capital_usd,
            unrealized_pnl_usd=0.0,
            cumulative_fees_usd=opt_fees,
            active_orders_count=1 if opt_spread else 0,
            open_positions_count=len(options_positions or {}),
            status="ACTIVE (Weekly Rebalance)",
        )

        return {
            "timestamp_utc": now_utc,
            "total_account_equity": account_equity,
            "sleeves": {
                "equities": eq_telemetry,
                "crypto": crypto_telemetry,
                "options": options_telemetry,
            },
            "crypto_eval": crypto_res,
            "options_eval": options_res,
        }
