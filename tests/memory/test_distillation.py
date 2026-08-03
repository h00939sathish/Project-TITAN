"""Unit tests for Semantic Rule Distillation Engine."""

import pytest
from titan.memory.vector_memory import VectorTradeMemory, TradeMemoryRecord
from titan.memory.distillation import RuleDistiller, RuleCandidate


class TestRuleDistiller:
    def test_distill_rules_from_trade_memory(self):
        mem = VectorTradeMemory()

        # Add 3 winning trades in TRENDING_UP regime
        for i in range(3):
            mem.store_trade(
                TradeMemoryRecord(
                    trade_id=f"win-{i}",
                    strategy_id="momentum",
                    instrument_id="AAPL",
                    entry_price=100.0,
                    exit_price=110.0,
                    pnl=100.0,
                    return_pct=0.10,
                    holding_period_seconds=3600.0,
                    regime_tags=["TRENDING_UP"],
                    reflection_note="Good trend",
                )
            )

        # Add 3 losing trades in HIGH_VOLATILITY regime
        for i in range(3):
            mem.store_trade(
                TradeMemoryRecord(
                    trade_id=f"loss-{i}",
                    strategy_id="mean_reversion",
                    instrument_id="SPY",
                    entry_price=400.0,
                    exit_price=390.0,
                    pnl=-100.0,
                    return_pct=-0.025,
                    holding_period_seconds=1800.0,
                    regime_tags=["HIGH_VOLATILITY"],
                    reflection_note="Stop loss hit",
                )
            )

        distiller = RuleDistiller(min_sample_size=3, min_win_rate=0.50)
        rules = distiller.distill_rules(mem)

        assert len(rules) == 1
        rule = rules[0]
        assert rule.regime_tag == "TRENDING_UP"
        assert rule.win_rate == 1.0
        assert rule.sample_size == 3
        assert rule.recommendation == "FAVORABLE"
