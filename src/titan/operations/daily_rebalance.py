"""Daily Rebalance Pipeline for Project TITAN Alpaca Retail Engine.

Executes point-in-time factor rebalancing at 10:30 AM ET (avoiding open volatility),
enforcing Alpaca compliance gates, capital tiering, and 100ms order rate pacing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

from titan.execution.alpaca_batch import (
    AlpacaBatchDispatcher,
    BatchExecutionReceipt,
)
from titan.research.pead_factor import (
    calculate_pead_factor,
    calculate_quality_lowbeta_factor,
    composite_alpha_scores,
    generate_target_weights,
)
from titan.risk.alpaca_compliance import AlpacaAccountTier, AlpacaComplianceGate


@dataclass(frozen=True)
class RebalanceSummary:
    """Immutable audit trail of a daily rebalance cycle."""
    timestamp_utc: str
    account_equity: float
    tier: int
    gross_exposure: float
    net_exposure: float
    compliance_approved: bool
    rejection_reasons: tuple[str, ...]
    orders_authorized: int
    orders_rejected: int
    orders_dispatched: int
    dispatched_orders: tuple[dict[str, Any], ...]


class DailyRebalanceOrchestrator:
    """Coordinates daily factor evaluation, compliance verification, and order execution."""

    def __init__(
        self,
        compliance_gate: Optional[AlpacaComplianceGate] = None,
        batch_dispatcher: Optional[AlpacaBatchDispatcher] = None,
        broker_client: Any = None,
        pacing_delay_seconds: float = 0.10,
    ):
        self.compliance_gate = compliance_gate or AlpacaComplianceGate()
        self.batch_dispatcher = batch_dispatcher or AlpacaBatchDispatcher(
            compliance_gate=self.compliance_gate,
            broker_client=broker_client,
            pacing_delay_seconds=pacing_delay_seconds,
        )

    def execute_daily_cycle(
        self,
        prices_df: pd.DataFrame,
        current_positions: Mapping[str, int],
        current_prices: Mapping[str, float],
        account_equity: float,
        *,
        events_df: Optional[pd.DataFrame] = None,
        etb_symbols: Optional[Sequence[str]] = None,
        top_k: int = 5,
        bottom_k: int = 5,
    ) -> RebalanceSummary:
        """Executes a single daily rebalance evaluation and dispatch cycle."""
        now_utc = datetime.now(timezone.utc).isoformat()
        equity_dec = Decimal(str(account_equity))

        # 1. Pre-execution PDT Capital Compliance Check
        tier = self.compliance_gate.get_account_tier(equity_dec)
        if tier == AlpacaAccountTier.RESTRICTED:
            reason = (
                f"REJECTED: Account equity (${account_equity:.2f}) is within 5% PDT buffer "
                f"(${self.compliance_gate.config.pdt_buffer_equity:.2f}). Rebalance frozen."
            )
            return RebalanceSummary(
                timestamp_utc=now_utc,
                account_equity=account_equity,
                tier=2,
                gross_exposure=0.0,
                net_exposure=0.0,
                compliance_approved=False,
                rejection_reasons=(reason,),
                orders_authorized=0,
                orders_rejected=1,
                orders_dispatched=0,
                dispatched_orders=(),
            )

        # 2. Factor Signal Generation
        pead_scores = calculate_pead_factor(prices_df, events_df=events_df)
        quality_scores = calculate_quality_lowbeta_factor(prices_df)
        composite = composite_alpha_scores(pead_scores, quality_scores)
        latest_scores = composite.iloc[-1]

        # 3. Quantile Target Portfolio Weights
        portfolio = generate_target_weights(
            scores_slice=latest_scores,
            capital_usd=account_equity,
            etb_symbols=etb_symbols,
            top_k=top_k,
            bottom_k=bottom_k,
            gross_exposure=1.0,
        )

        # 4. Dispatch with 100ms pacing and compliance checks
        etb_status = {s: True for s in etb_symbols} if etb_symbols else None
        receipt: BatchExecutionReceipt = self.batch_dispatcher.execute_rebalance(
            target_weights=portfolio.weights,
            current_prices=dict(current_prices),
            total_equity=equity_dec,
            current_positions=dict(current_positions),
            etb_status=etb_status,
        )

        reasons = tuple(f"{sym}: {msg}" for sym, msg in receipt.rejections)
        approved = (receipt.orders_rejected == 0) and (receipt.orders_dispatched > 0 or len(portfolio.weights) == 0)

        return RebalanceSummary(
            timestamp_utc=now_utc,
            account_equity=account_equity,
            tier=portfolio.tier,
            gross_exposure=portfolio.gross_exposure,
            net_exposure=portfolio.net_exposure,
            compliance_approved=approved,
            rejection_reasons=reasons,
            orders_authorized=receipt.orders_authorized,
            orders_rejected=receipt.orders_rejected,
            orders_dispatched=receipt.orders_dispatched,
            dispatched_orders=tuple(receipt.dispatched_orders),
        )
